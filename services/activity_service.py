from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Callable, Iterable

from repositories.decimal_storage import DecimalStorage


@dataclass(frozen=True)
class Activity:
    occurred_at: str
    module: str
    kind: str
    description: str
    user: str = "Sistema"
    record_id: str = ""
    action: str = ""


class ActivityService:
    """Consulta atividades recentes sem alterar o schema existente."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection],
        *,
        backup_directory: str | Path | None = None,
        log_directory: str | Path | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.backup_directory = Path(backup_directory) if backup_directory else None
        self.log_directory = Path(log_directory) if log_directory else None

    @staticmethod
    def _tables(connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {str(row[0]) for row in rows}

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}

    @staticmethod
    def _normalize_date(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                return datetime.strptime(text[:19], fmt).isoformat(timespec="seconds")
            except ValueError:
                continue
        return text

    @staticmethod
    def _within_period(occurred_at: str, days: int | None, now: datetime) -> bool:
        if not days or days <= 0 or not occurred_at:
            return True
        try:
            parsed = datetime.fromisoformat(occurred_at)
        except ValueError:
            return True
        return parsed >= now - timedelta(days=days)

    def _query(self, connection: sqlite3.Connection, sql: str, params: Iterable[object] = ()) -> list[sqlite3.Row]:
        try:
            return connection.execute(sql, tuple(params)).fetchall()
        except sqlite3.Error:
            return []

    def list_activities(
        self,
        *,
        days: int | None = 30,
        module: str = "",
        user: str = "",
        allowed_modules: set[str] | None = None,
        limit: int = 100,
        now: datetime | None = None,
    ) -> list[Activity]:
        now = now or datetime.now()
        activities: list[Activity] = []
        connection = self.connection_factory()
        previous_factory = getattr(connection, "row_factory", None)
        connection.row_factory = sqlite3.Row
        try:
            tables = self._tables(connection)

            if "movimentacoes" in tables:
                rows = self._query(connection, """
                    SELECT id, data, tipo, descricao, valor, status_pagamento
                    FROM movimentacoes ORDER BY id DESC LIMIT 80
                """)
                for row in rows:
                    kind = "Venda" if str(row["tipo"] or "").upper() == "COMPRA" else str(row["tipo"] or "Movimentação").title()
                    activities.append(Activity(
                        self._normalize_date(row["data"]), "Vendas", kind,
                        f"{row['descricao'] or 'Movimentação'} — R$ {DecimalStorage.to_decimal(row['valor'] or 0, field='valor da movimentação'):.2f}",
                        record_id=str(row["id"]), action="open_movement",
                    ))

            if "clientes" in tables:
                columns = self._columns(connection, "clientes")
                date_column = "criado_em" if "criado_em" in columns else ""
                select_date = date_column if date_column else "''"
                rows = self._query(connection, f"SELECT id, nome, {select_date} AS ocorrido FROM clientes ORDER BY id DESC LIMIT 30")
                for row in rows:
                    activities.append(Activity(self._normalize_date(row["ocorrido"]), "Clientes", "Cadastro", str(row["nome"] or "Cliente"), record_id=str(row["id"]), action="open_client"))

            if "produtos" in tables:
                rows = self._query(connection, "SELECT id, nome, criado_em FROM produtos ORDER BY id DESC LIMIT 30")
                for row in rows:
                    activities.append(Activity(self._normalize_date(row["criado_em"]), "Produtos", "Cadastro", str(row["nome"] or "Produto"), record_id=str(row["id"]), action="open_product"))

                product_columns = self._columns(connection, "produtos")
                if {"estoque_atual", "estoque_minimo"}.issubset(product_columns):
                    rows = self._query(connection, """
                        SELECT id, nome, estoque_atual, estoque_minimo, atualizado_em
                        FROM produtos WHERE ativo=1 AND controla_estoque=1
                          AND estoque_atual <= estoque_minimo
                        ORDER BY (estoque_minimo-estoque_atual) DESC LIMIT 30
                    """)
                    for row in rows:
                        activities.append(Activity(
                            self._normalize_date(row["atualizado_em"]), "Estoque", "Estoque baixo",
                            f"{row['nome']} — saldo {float(row['estoque_atual'] or 0):g}, mínimo {float(row['estoque_minimo'] or 0):g}",
                            record_id=str(row["id"]), action="open_product",
                        ))

            if "nfe_importacoes" in tables:
                rows = self._query(connection, """
                    SELECT id, numero, fornecedor_nome, status, data_importacao
                    FROM nfe_importacoes ORDER BY id DESC LIMIT 40
                """)
                for row in rows:
                    status = str(row["status"] or "Importada")
                    activities.append(Activity(
                        self._normalize_date(row["data_importacao"]), "XML", f"NF-e {status.title()}",
                        f"NF-e {row['numero'] or 'sem número'} — {row['fornecedor_nome'] or 'fornecedor não informado'}",
                        record_id=str(row["id"]), action="open_nfe_history",
                    ))

            if "titulos_financeiros" in tables:
                rows = self._query(connection, """
                    SELECT id, pessoa_nome, descricao, data_vencimento, valor_original, atualizado_em
                    FROM titulos_financeiros
                    WHERE status IN ('ABERTO','PARCIAL') AND data_vencimento < ?
                    ORDER BY data_vencimento ASC LIMIT 40
                """, (now.strftime("%Y-%m-%d"),))
                for row in rows:
                    activities.append(Activity(
                        self._normalize_date(row["atualizado_em"] or row["data_vencimento"]), "Financeiro", "Conta vencida",
                        f"{row['pessoa_nome'] or row['descricao'] or 'Título'} — R$ {DecimalStorage.to_decimal(row['valor_original'] or 0, field='valor do título'):.2f}",
                        record_id=str(row["id"]), action="open_finance",
                    ))

            if "auditoria" in tables:
                columns = self._columns(connection, "auditoria")
                required = {"id", "data", "acao"}
                if required.issubset(columns):
                    user_expr = "usuario" if "usuario" in columns else "'Sistema'"
                    details_expr = "detalhes" if "detalhes" in columns else "''"
                    rows = self._query(connection, f"SELECT id, data, acao, {details_expr} AS detalhes, {user_expr} AS usuario FROM auditoria ORDER BY id DESC LIMIT 50")
                    for row in rows:
                        activities.append(Activity(self._normalize_date(row["data"]), "Sistema", str(row["acao"] or "Auditoria"), str(row["detalhes"] or ""), str(row["usuario"] or "Sistema"), str(row["id"])))
        finally:
            connection.row_factory = previous_factory
            connection.close()

        activities.extend(self._file_activities(self.backup_directory, "Backup", "Backup realizado"))
        activities.extend(self._file_activities(self.log_directory, "Sistema", "Erro ou aviso", suffixes={".log", ".txt"}))

        module_filter = module.strip().casefold()
        user_filter = user.strip().casefold()
        filtered = [activity for activity in activities if self._within_period(activity.occurred_at, days, now)]
        if module_filter:
            filtered = [activity for activity in filtered if activity.module.casefold() == module_filter]
        if user_filter:
            filtered = [activity for activity in filtered if activity.user.casefold() == user_filter]
        if allowed_modules is not None:
            normalized_allowed = {str(item).strip().casefold() for item in allowed_modules}
            filtered = [activity for activity in filtered if activity.module.casefold() in normalized_allowed]
        filtered.sort(key=lambda item: item.occurred_at or "0000", reverse=True)
        return filtered[:max(1, int(limit))]

    def _file_activities(self, directory: Path | None, module: str, kind: str, *, suffixes: set[str] | None = None) -> list[Activity]:
        if directory is None or not directory.exists():
            return []
        results: list[Activity] = []
        try:
            files = [path for path in directory.iterdir() if path.is_file()]
        except OSError:
            return []
        if suffixes:
            files = [path for path in files if path.suffix.casefold() in suffixes]
        for path in sorted(files, key=lambda item: item.stat().st_mtime, reverse=True)[:20]:
            try:
                occurred_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            except OSError:
                continue
            results.append(Activity(occurred_at, module, kind, path.name))
        return results
