from __future__ import annotations

import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from repositories.decimal_storage import DecimalStorage
from database.sqlite_introspection import table_exists
from services.windows_pdf_printer import WindowsPDFPrinter


@dataclass(frozen=True)
class ReportResult:
    report_id: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    filters: dict[str, Any]
    generated_at: str

    @property
    def row_count(self) -> int:
        return len(self.rows)


class ReportService:
    """Relatórios filtrados e exportáveis sem alterar o schema do banco."""

    HISTORY_KEY = "reports.history.v1"
    SCHEDULES_KEY = "reports.schedules.v1"
    CUSTOM_INDICATORS_KEY = "reports.custom_indicators.v1"
    MAX_HISTORY = 200

    REPORTS = {
        "vendas": "Vendas por período",
        "recebimentos": "Recebimentos de fichas por período",
        "produtos": "Produtos e estoque",
        "clientes": "Clientes e saldos",
        "financeiro": "Títulos financeiros",
        "compras": "Pedidos de compra",
        "nfe": "NF-e importadas",
        "estoque": "Movimentações de estoque",
    }

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection],
        *,
        output_dir: str | Path,
        audit: Callable[..., None] | None = None,
        authorize: Callable[[str, str], bool] | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audit = audit
        self.authorize = authorize

    @classmethod
    def available_reports(cls) -> dict[str, str]:
        return dict(cls.REPORTS)

    def generate(
        self,
        report_id: str,
        *,
        start_date: str = "",
        end_date: str = "",
        search: str = "",
        status: str = "",
        user: str = "",
        limit: int = 5000,
        offset: int = 0,
        actor: str = "Sistema",
    ) -> ReportResult:
        report_id = str(report_id).strip().lower()
        if report_id not in self.REPORTS:
            raise ValueError("Relatório desconhecido.")
        if self.authorize and not self.authorize(actor, report_id):
            raise PermissionError("Usuário sem permissão para este relatório.")
        start = self._normalize_date(start_date, end=False)
        end = self._normalize_date(end_date, end=True)
        safe_limit = min(max(int(limit), 1), 50_000)
        safe_offset = max(int(offset), 0)
        filters = {
            "start_date": start_date.strip(), "end_date": end_date.strip(),
            "search": search.strip(), "status": status.strip(), "user": user.strip(),
            "limit": safe_limit, "offset": safe_offset,
        }
        connection = self.connection_factory()
        try:
            columns, rows = getattr(self, f"_report_{report_id}")(
                connection, start=start, end=end, search=search.strip(), status=status.strip(), user=user.strip(), limit=safe_limit, offset=safe_offset
            )
        finally:
            connection.close()
        result = ReportResult(
            report_id=report_id,
            title=self.REPORTS[report_id],
            columns=tuple(columns),
            rows=tuple(tuple(row) for row in rows),
            filters=filters,
            generated_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._append_history({
            "report_id": result.report_id,
            "title": result.title,
            "generated_at": result.generated_at,
            "row_count": result.row_count,
            "filters": result.filters,
            "format": "PREVIEW",
            "path": "",
            "user": actor,
        })
        self._audit(actor, "GERAR", result.report_id, f"linhas={result.row_count}")
        return result

    def count(self, report_id: str, **filters) -> int:
        _columns, rows = self._aggregate(report_id, **filters)
        return int(rows[0][0]) if rows else 0

    def generate_page(self, report_id: str, *, limit: int, offset: int = 0,
                      actor: str = "Sistema", **filters):
        result = self.generate(report_id, limit=limit, offset=offset, actor=actor, **filters)
        _columns, aggregate = self._aggregate(report_id, **filters)
        quantity = int(aggregate[0][0]) if aggregate else 0
        value_total = DecimalStorage.to_decimal(aggregate[0][1] if aggregate else 0, field="valor total")
        return result, {"quantidade": quantity, "valor_total": value_total}, quantity

    def _aggregate(self, report_id: str, **filters):
        report_id = str(report_id).strip().lower()
        if report_id not in self.REPORTS:
            raise ValueError("Relatório desconhecido.")
        options = {
            "start": self._normalize_date(str(filters.get("start_date") or ""), end=False),
            "end": self._normalize_date(str(filters.get("end_date") or ""), end=True),
            "search": str(filters.get("search") or "").strip(),
            "status": str(filters.get("status") or "").strip(),
            "user": str(filters.get("user") or "").strip(), "aggregate": True,
        }
        connection = self.connection_factory()
        try:
            return getattr(self, f"_report_{report_id}")(connection, **options)
        finally:
            connection.close()

    def indicators(self, *, start_date: str = "", end_date: str = "") -> dict[str, Decimal | int]:
        start = self._normalize_date(start_date, end=False)
        end = self._normalize_date(end_date, end=True)
        connection = self.connection_factory()
        try:
            indicators: dict[str, Decimal | int] = {
                "vendas_total": Decimal("0"), "vendas_quantidade": 0,
                "receber_aberto": Decimal("0"), "pagar_aberto": Decimal("0"),
                "estoque_baixo": 0, "clientes_ativos": 0,
            }
            if self._table_exists(connection, "movimentacoes"):
                cols = self._columns(connection, "movimentacoes")
                date_col = self._first(cols, "data", "data_movimentacao", "criado_em")
                value_col = self._first(cols, "valor_total", "valor", "total")
                type_col = self._first(cols, "tipo", "origem")
                where, params = self._date_where(date_col, start, end)
                if type_col:
                    # Venda reconhece faturamento uma única vez. Recebimentos de
                    # fichas apenas liquidam o contas a receber e não são nova venda.
                    where.append(f"UPPER(COALESCE({type_col},'')) IN ('COMPRA','VENDA')")
                sql_where = " WHERE " + " AND ".join(where) if where else ""
                value_expr = value_col or "0"
                row = connection.execute(f"SELECT COUNT(*), COALESCE(SUM({value_expr}),0) FROM movimentacoes{sql_where}", params).fetchone()
                indicators["vendas_quantidade"] = int(row[0] or 0)
                indicators["vendas_total"] = DecimalStorage.to_decimal(row[1] or 0, field="total de vendas")
            if self._table_exists(connection, "financeiro_titulos"):
                cols = self._columns(connection, "financeiro_titulos")
                if {"tipo", "status", "valor_original", "valor_pago"}.issubset(cols):
                    for tipo, key in (("RECEBER", "receber_aberto"), ("PAGAR", "pagar_aberto")):
                        row = connection.execute(
                            "SELECT COALESCE(SUM(valor_original-valor_pago),0) FROM financeiro_titulos WHERE tipo=? AND status NOT IN ('PAGO','CANCELADO')",
                            (tipo,),
                        ).fetchone()
                        indicators[key] = DecimalStorage.to_decimal(row[0] or 0, field=key)
            if self._table_exists(connection, "produtos"):
                cols = self._columns(connection, "produtos")
                if {"estoque_atual", "estoque_minimo"}.issubset(cols):
                    row = connection.execute("SELECT COUNT(*) FROM produtos WHERE ativo=1 AND controla_estoque=1 AND estoque_atual<=estoque_minimo").fetchone()
                    indicators["estoque_baixo"] = int(row[0] or 0)
            if self._table_exists(connection, "clientes"):
                cols = self._columns(connection, "clientes")
                clause = " WHERE ativo=1" if "ativo" in cols else ""
                indicators["clientes_ativos"] = int(connection.execute(f"SELECT COUNT(*) FROM clientes{clause}").fetchone()[0] or 0)
            return indicators
        finally:
            connection.close()

    @staticmethod
    def result_summary(result: ReportResult) -> dict[str, Decimal | int]:
        """Totaliza somente a coluna monetária oficial do relatório exibido."""
        candidates = ("valor_total", "valor", "total")
        value_column = next((name for name in candidates if name in result.columns), None)
        total = Decimal("0")
        if value_column is not None:
            position = result.columns.index(value_column)
            for row in result.rows:
                total += DecimalStorage.to_decimal(row[position] or 0, field="valor do relatório")
        return {"quantidade": result.row_count, "valor_total": total}


    def chart_series(self, result: ReportResult, *, max_categories: int = 12) -> dict[str, Any]:
        """Converte um relatório em uma série categórica segura para gráficos."""
        if not result.columns or not result.rows:
            return {"title": result.title, "labels": [], "values": [], "value_column": ""}
        numeric_index = None
        for index, column in enumerate(result.columns):
            values = [row[index] for row in result.rows if index < len(row)]
            convertible = 0
            for value in values:
                try:
                    float(value)
                    convertible += 1
                except (TypeError, ValueError):
                    pass
            if values and convertible >= max(1, len(values) // 2):
                numeric_index = index
                if any(token in column.casefold() for token in ("valor", "total", "saldo", "quantidade", "estoque", "preco", "custo")):
                    break
        if numeric_index is None:
            numeric_index = 0
        label_index = 0 if numeric_index != 0 else (1 if len(result.columns) > 1 else 0)
        aggregate: dict[str, float] = {}
        for row in result.rows:
            if numeric_index >= len(row):
                continue
            label = str(row[label_index] if label_index < len(row) else "").strip() or "Sem identificação"
            try:
                value = float(row[numeric_index] or 0)
            except (TypeError, ValueError):
                value = 1.0
            aggregate[label] = aggregate.get(label, 0.0) + value
        ordered = sorted(aggregate.items(), key=lambda item: abs(item[1]), reverse=True)[:max(1, int(max_categories))]
        return {
            "title": result.title,
            "labels": [item[0] for item in ordered],
            "values": [item[1] for item in ordered],
            "value_column": result.columns[numeric_index],
        }

    def dashboard(self, *, start_date: str = "", end_date: str = "") -> dict[str, Any]:
        indicators = self.indicators(start_date=start_date, end_date=end_date)
        sales = self.generate("vendas", start_date=start_date, end_date=end_date, limit=5000, actor="Sistema")
        return {
            "indicators": indicators,
            "custom_indicators": self.evaluate_custom_indicators(start_date=start_date, end_date=end_date),
            "sales_chart": self.chart_series(sales),
        }

    def list_custom_indicators(self) -> list[dict[str, Any]]:
        data = self._load_json_setting(self.CUSTOM_INDICATORS_KEY, [])
        return sorted((dict(row) for row in data if isinstance(row, Mapping)), key=lambda row: str(row.get("name", "")).casefold())

    def save_custom_indicator(self, definition: Mapping[str, Any], *, actor: str = "Sistema") -> dict[str, Any]:
        name = str(definition.get("name", "")).strip()
        report_id = str(definition.get("report_id", "")).strip().lower()
        aggregation = str(definition.get("aggregation", "COUNT")).strip().upper()
        column = str(definition.get("column", "")).strip()
        if not name:
            raise ValueError("Informe o nome do indicador.")
        if report_id not in self.REPORTS:
            raise ValueError("Relatório inválido para o indicador.")
        if aggregation not in {"COUNT", "SUM", "AVG", "MIN", "MAX"}:
            raise ValueError("Agregação inválida.")
        sample = self.generate(report_id, limit=1, actor=actor)
        if aggregation != "COUNT" and column not in sample.columns:
            raise ValueError("Coluna inválida para o indicador.")
        normalized = {
            "name": name,
            "report_id": report_id,
            "aggregation": aggregation,
            "column": column if aggregation != "COUNT" else "",
            "filters": dict(definition.get("filters") or {}),
            "active": bool(definition.get("active", True)),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "updated_by": actor,
        }
        rows = [row for row in self.list_custom_indicators() if str(row.get("name", "")).casefold() != name.casefold()]
        rows.append(normalized)
        self._save_json_setting(self.CUSTOM_INDICATORS_KEY, rows)
        self._audit(actor, "SALVAR_INDICADOR", name, f"relatorio={report_id}; agregacao={aggregation}; coluna={column}")
        return normalized

    def delete_custom_indicator(self, name: str, *, actor: str = "Sistema") -> None:
        original = self.list_custom_indicators()
        filtered = [row for row in original if str(row.get("name", "")).casefold() != str(name).strip().casefold()]
        if len(filtered) == len(original):
            raise ValueError("Indicador inexistente.")
        self._save_json_setting(self.CUSTOM_INDICATORS_KEY, filtered)
        self._audit(actor, "EXCLUIR_INDICADOR", str(name), "")

    def evaluate_custom_indicators(self, *, start_date: str = "", end_date: str = "") -> list[dict[str, Any]]:
        evaluated: list[dict[str, Any]] = []
        for definition in self.list_custom_indicators():
            if not definition.get("active", True):
                continue
            filters = dict(definition.get("filters") or {})
            if start_date:
                filters["start_date"] = start_date
            if end_date:
                filters["end_date"] = end_date
            result = self.generate(
                str(definition.get("report_id", "")),
                start_date=str(filters.get("start_date", "")), end_date=str(filters.get("end_date", "")),
                search=str(filters.get("search", "")), status=str(filters.get("status", "")),
                user=str(filters.get("user", "")), limit=50_000, actor="Sistema",
            )
            aggregation = str(definition.get("aggregation", "COUNT")).upper()
            column = str(definition.get("column", ""))
            if aggregation == "COUNT":
                value: Decimal | int = result.row_count
            else:
                index = result.columns.index(column)
                values: list[Decimal] = []
                for row in result.rows:
                    try:
                        values.append(DecimalStorage.to_decimal(row[index] or 0, field=column))
                    except (TypeError, ValueError):
                        continue
                if not values:
                    value = Decimal("0")
                elif aggregation == "SUM":
                    value = sum(values)
                elif aggregation == "AVG":
                    value = sum(values) / len(values)
                elif aggregation == "MIN":
                    value = min(values)
                else:
                    value = max(values)
            evaluated.append({**definition, "value": value, "evaluated_at": datetime.now().isoformat(timespec="seconds")})
        return evaluated

    def export(self, result: ReportResult, fmt: str, destination: str | Path | None = None, *, actor: str = "Sistema") -> Path:
        fmt = str(fmt).strip().upper()
        if fmt not in {"CSV", "XLSX", "PDF"}:
            raise ValueError("Formato de exportação inválido.")
        extension = {"CSV": ".csv", "XLSX": ".xlsx", "PDF": ".pdf"}[fmt]
        if destination is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = self.output_dir / f"{result.report_id}_{stamp}{extension}"
        path = Path(destination).expanduser().resolve()
        if path.suffix.lower() != extension:
            path = path.with_suffix(extension)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=path.stem + ".", suffix=extension, dir=str(path.parent)
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            if fmt == "CSV":
                self._export_csv(result, temporary_path)
            elif fmt == "XLSX":
                self._export_xlsx(result, temporary_path)
            else:
                self._export_pdf(result, temporary_path)
            if not temporary_path.is_file() or temporary_path.stat().st_size <= 0:
                raise RuntimeError("A exportação não gerou um arquivo válido.")
            os.replace(temporary_path, path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        self._append_history({
            "report_id": result.report_id, "title": result.title,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "row_count": result.row_count, "filters": result.filters,
            "format": fmt, "path": str(path), "user": actor,
        })
        self._audit(actor, "EXPORTAR", result.report_id, f"formato={fmt}; caminho={path}")
        return path

    def print_pdf(
        self,
        result: ReportResult,
        destination: str | Path | None = None,
        *,
        actor: str = "Sistema",
        dispatch: bool = True,
    ) -> Path:
        path = self.export(result, "PDF", destination, actor=actor)
        if dispatch:
            self._dispatch_print(path)
            self._audit(actor, "IMPRIMIR", result.report_id, f"caminho={path}")
        return path

    @staticmethod
    def _dispatch_print(path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(path)
        if sys.platform.startswith("win"):
            WindowsPDFPrinter().print(path, "Padrão do Sistema")
            return
        command = shutil.which("lp") or shutil.which("lpr")
        if not command:
            raise RuntimeError("Nenhum comando de impressão (lp/lpr) está disponível.")
        completed = subprocess.run([command, str(path)], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "Falha ao enviar para impressão.").strip())

    def history_entry(self, index: int) -> dict[str, Any]:
        rows = self.history(limit=self.MAX_HISTORY)
        if index < 0 or index >= len(rows):
            raise IndexError("Registro de histórico inválido.")
        return dict(rows[index])

    def history(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._load_json_setting(self.HISTORY_KEY, [])
        if not isinstance(rows, list):
            return []
        valid = [dict(item) for item in rows if isinstance(item, dict)]
        return list(reversed(valid))[0:max(1, int(limit))]

    def clear_history(self, *, actor: str = "Sistema") -> None:
        self._save_json_setting(self.HISTORY_KEY, [])
        self._audit(actor, "LIMPAR_HISTORICO", "relatorios", "")

    def list_schedules(self) -> list[dict[str, Any]]:
        data = self._load_json_setting(self.SCHEDULES_KEY, [])
        if not isinstance(data, list):
            return []
        valid: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if not str(row.get("name", "")).strip():
                continue
            if str(row.get("report_id", "")).strip().lower() not in self.REPORTS:
                continue
            if str(row.get("frequency", "")).strip().upper() not in {"DIARIO", "SEMANAL", "MENSAL"}:
                continue
            if str(row.get("format", "CSV")).strip().upper() not in {"CSV", "XLSX", "PDF"}:
                continue
            valid.append(row)
        return sorted(valid, key=lambda row: str(row.get("name", "")).casefold())

    def save_schedule(self, schedule: Mapping[str, Any], *, actor: str = "Sistema") -> dict[str, Any]:
        name = str(schedule.get("name", "")).strip()
        report_id = str(schedule.get("report_id", "")).strip().lower()
        frequency = str(schedule.get("frequency", "")).strip().upper()
        fmt = str(schedule.get("format", "CSV")).strip().upper()
        if not name:
            raise ValueError("Informe o nome do agendamento.")
        if report_id not in self.REPORTS:
            raise ValueError("Relatório inválido.")
        if frequency not in {"DIARIO", "SEMANAL", "MENSAL"}:
            raise ValueError("Frequência inválida.")
        if fmt not in {"CSV", "XLSX", "PDF"}:
            raise ValueError("Formato inválido.")
        run_time = str(schedule.get("run_time", "08:00")).strip() or "08:00"
        try:
            datetime.strptime(run_time, "%H:%M")
        except ValueError as exc:
            raise ValueError("Horário inválido. Use HH:MM.") from exc
        now = datetime.now()
        normalized = {
            "name": name,
            "report_id": report_id,
            "frequency": frequency,
            "format": fmt,
            "active": bool(schedule.get("active", True)),
            "filters": dict(schedule.get("filters") or {}),
            "run_time": run_time,
            "last_run_at": str(schedule.get("last_run_at", "")),
            "next_run_at": str(schedule.get("next_run_at", "")) or self._next_run_at(frequency, run_time, now).isoformat(timespec="minutes"),
            "updated_at": now.isoformat(timespec="seconds"),
            "updated_by": actor,
        }
        schedules = self.list_schedules()
        schedules = [row for row in schedules if str(row.get("name", "")).casefold() != name.casefold()]
        schedules.append(normalized)
        self._save_json_setting(self.SCHEDULES_KEY, schedules)
        self._audit(actor, "SALVAR_AGENDAMENTO", name, f"relatorio={report_id}; frequencia={frequency}")
        return normalized

    def delete_schedule(self, name: str, *, actor: str = "Sistema") -> None:
        original = self.list_schedules()
        filtered = [row for row in original if str(row.get("name", "")).casefold() != str(name).strip().casefold()]
        if len(filtered) == len(original):
            raise ValueError("Agendamento inexistente.")
        self._save_json_setting(self.SCHEDULES_KEY, filtered)
        self._audit(actor, "EXCLUIR_AGENDAMENTO", name, "")

    def run_schedule(self, name: str, *, actor: str = "Sistema") -> Path:
        schedule = next((row for row in self.list_schedules() if str(row.get("name", "")).casefold() == str(name).strip().casefold()), None)
        if not schedule:
            raise ValueError("Agendamento inexistente.")
        if not schedule.get("active", True):
            raise ValueError("Agendamento inativo.")
        filters = dict(schedule.get("filters") or {})
        result = self.generate(schedule["report_id"], actor=actor, **{k: filters.get(k, "") for k in ("start_date", "end_date", "search", "status", "user")})
        path = self.export(result, schedule["format"], actor=actor)
        schedules = self.list_schedules()
        now = datetime.now()
        for row in schedules:
            if str(row.get("name", "")).casefold() == str(name).strip().casefold():
                row["last_run_at"] = now.isoformat(timespec="seconds")
                row["next_run_at"] = self._next_run_at(str(row.get("frequency", "")), str(row.get("run_time", "08:00")), now + timedelta(minutes=1)).isoformat(timespec="minutes")
        self._save_json_setting(self.SCHEDULES_KEY, schedules)
        return path

    def run_due_schedules(self, *, now: datetime | None = None, actor: str = "Sistema") -> list[Path]:
        current = now or datetime.now()
        generated: list[Path] = []
        for schedule in self.list_schedules():
            if not schedule.get("active", True):
                continue
            raw_next = str(schedule.get("next_run_at", "")).strip()
            try:
                next_run = datetime.fromisoformat(raw_next) if raw_next else self._next_run_at(str(schedule.get("frequency", "")), str(schedule.get("run_time", "08:00")), current)
            except ValueError:
                next_run = current
            if next_run <= current:
                name = str(schedule.get("name", ""))
                try:
                    generated.append(self.run_schedule(name, actor=actor))
                except Exception as exc:
                    if self.audit:
                        self.audit(
                            "relatorios", "EXECUTAR_AGENDAMENTO", name,
                            str(exc), "ERRO", actor,
                        )
        return generated

    @staticmethod
    def _next_run_at(frequency: str, run_time: str, base: datetime) -> datetime:
        hour, minute = (int(part) for part in run_time.split(":", 1))
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base:
            if frequency == "DIARIO":
                candidate += timedelta(days=1)
            elif frequency == "SEMANAL":
                candidate += timedelta(days=7)
            elif frequency == "MENSAL":
                import calendar
                year = candidate.year + (1 if candidate.month == 12 else 0)
                month = 1 if candidate.month == 12 else candidate.month + 1
                day = min(candidate.day, calendar.monthrange(year, month)[1])
                candidate = candidate.replace(year=year, month=month, day=day)
            else:
                raise ValueError("Frequência inválida.")
        return candidate

    def _report_vendas(self, connection, **kwargs):
        return self._generic_report(
            connection, "movimentacoes", kwargs,
            preferred=("id", "data", "tipo", "cliente", "descricao", "valor_total", "valor", "forma_pagamento", "status", "usuario"),
            required_types=("COMPRA", "VENDA"),
        )

    def _report_recebimentos(self, connection, **kwargs):
        return self._generic_report(
            connection, "movimentacoes", kwargs,
            preferred=("id", "data", "tipo", "cliente", "descricao", "valor_total", "valor", "forma_pagamento", "status", "usuario"),
            required_types=("PAGAMENTO", "RECEBIMENTO"),
        )

    def _report_produtos(self, connection, **kwargs):
        return self._generic_report(connection, "produtos", kwargs, preferred=("id", "codigo", "codigo_barras", "nome", "preco_custo", "preco_venda", "estoque_atual", "estoque_minimo", "ativo", "atualizado_em"))

    def _report_clientes(self, connection, **kwargs):
        return self._generic_report(connection, "clientes", kwargs, preferred=("id", "nome", "cpf_cnpj", "telefone", "email", "saldo_devedor", "ativo", "data_cadastro", "atualizado_em"))

    def _report_financeiro(self, connection, **kwargs):
        return self._generic_report(connection, "financeiro_titulos", kwargs, preferred=("id", "tipo", "pessoa_nome", "descricao", "data_emissao", "data_vencimento", "valor_original", "valor_pago", "saldo_aberto", "status", "origem", "origem_id"))

    def _report_compras(self, connection, **kwargs):
        return self._generic_report(connection, "pedidos_compra", kwargs, preferred=("id", "fornecedor_id", "status", "observacao", "valor_total", "data_pedido", "data_recebimento", "criado_em"))

    def _report_nfe(self, connection, **kwargs):
        return self._generic_report(connection, "nfe_importacoes", kwargs, preferred=("id", "chave", "numero", "fornecedor_cnpj", "fornecedor_nome", "status", "valor_total", "itens_total", "itens_criados", "itens_vinculados", "data_importacao"))

    def _report_estoque(self, connection, **kwargs):
        return self._generic_report(connection, "estoque_movimentacoes", kwargs, preferred=("id", "produto_id", "tipo", "quantidade", "saldo_anterior", "saldo_atual", "origem", "origem_id", "motivo", "usuario", "data"))

    def _generic_report(
        self, connection, table: str, options: Mapping[str, Any], *,
        preferred: Sequence[str], required_types: Sequence[str] = (),
    ):
        if not self._table_exists(connection, table):
            return tuple(), tuple()
        columns = self._columns(connection, table)
        selected = [column for column in preferred if column in columns]
        if not selected:
            selected = sorted(columns)
        date_col = self._first(columns, "data", "data_emissao", "data_importacao", "data_pedido", "criado_em", "atualizado_em", "data_cadastro")
        status_col = self._first(columns, "status", "ativo", "tipo")
        user_col = self._first(columns, "usuario", "updated_by", "criado_por")
        text_cols = [column for column in selected if column not in {"id"}]
        where, params = self._date_where(date_col, options.get("start"), options.get("end"))
        if required_types and "tipo" in columns:
            normalized_types = tuple(str(item).strip().upper() for item in required_types)
            where.append(
                "UPPER(COALESCE(tipo,'')) IN (" + ",".join("?" for _ in normalized_types) + ")"
            )
            params.extend(normalized_types)
        search = str(options.get("search") or "").strip()
        if search and text_cols:
            where.append("(" + " OR ".join(f"CAST({column} AS TEXT) LIKE ?" for column in text_cols) + ")")
            params.extend([f"%{search}%"] * len(text_cols))
        status = str(options.get("status") or "").strip()
        if status and status_col:
            where.append(f"UPPER(CAST({status_col} AS TEXT))=UPPER(?)")
            params.append(status)
        user = str(options.get("user") or "").strip()
        if user and user_col:
            where.append(f"UPPER(CAST({user_col} AS TEXT))=UPPER(?)")
            params.append(user)
        aggregate = bool(options.get("aggregate"))
        value_col = self._first(columns, "valor_total", "valor", "total", "valor_original")
        projection = (
            f"COUNT(*), COALESCE(SUM({value_col}),0)" if aggregate and value_col
            else "COUNT(*), 0" if aggregate
            else ", ".join(selected)
        )
        sql = f"SELECT {projection} FROM {table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if aggregate:
            row = connection.execute(sql, params).fetchone()
            return ("quantidade", "valor_total"), ((row[0], row[1]),)
        if date_col:
            sql += f" ORDER BY {date_col} DESC"
            if "id" in columns and date_col != "id":
                sql += ", id DESC"
        elif "id" in columns:
            sql += " ORDER BY id DESC"
        sql += " LIMIT ? OFFSET ?"
        params.extend((int(options.get("limit") or 5000), max(0, int(options.get("offset") or 0))))
        rows = connection.execute(sql, params).fetchall()
        return tuple(selected), tuple(tuple(row[column] for column in selected) if hasattr(row, "keys") else tuple(row) for row in rows)

    @staticmethod
    def _export_csv(result: ReportResult, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(result.columns)
            writer.writerows(result.rows)

    @staticmethod
    def _export_xlsx(result: ReportResult, path: Path) -> None:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError as exc:
            raise RuntimeError("Instale openpyxl para exportar Excel.") from exc
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Relatório"
        sheet.append(list(result.columns))
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in result.rows:
            sheet.append(list(row))
        for column_cells in sheet.columns:
            max_length = min(max((len(str(cell.value or "")) for cell in column_cells), default=10) + 2, 60)
            sheet.column_dimensions[column_cells[0].column_letter].width = max_length
        workbook.save(path)

    @staticmethod
    def _export_pdf(result: ReportResult, path: Path) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        except ImportError as exc:
            raise RuntimeError("Instale reportlab para exportar PDF.") from exc
        page = landscape(A4) if len(result.columns) > 6 else A4
        document = SimpleDocTemplate(str(path), pagesize=page, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
        styles = getSampleStyleSheet()
        summary = ReportService.result_summary(result)
        total = DecimalStorage.canonical(summary["valor_total"], field="valor total do relatório")
        data = [list(result.columns)] + [["" if value is None else str(value) for value in row] for row in result.rows]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6feb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ]))
        document.build([
            Paragraph(result.title, styles["Title"]),
            Paragraph(f"Gerado em {result.generated_at} • {result.row_count} registro(s)", styles["Normal"]),
            Paragraph(f"Valor total do período: R$ {total}", styles["Normal"]),
            Spacer(1, 12), table,
        ])

    def _append_history(self, entry: dict[str, Any]) -> None:
        history = self._load_json_setting(self.HISTORY_KEY, [])
        if not isinstance(history, list):
            history = []
        history = [item for item in history if isinstance(item, dict)]
        history.append(entry)
        self._save_json_setting(self.HISTORY_KEY, history[-self.MAX_HISTORY:])

    def _load_json_setting(self, key: str, default: Any) -> Any:
        connection = self.connection_factory()
        try:
            if not self._table_exists(connection, "configuracoes"):
                return default
            row = connection.execute("SELECT valor FROM configuracoes WHERE chave=?", (key,)).fetchone()
            if not row:
                return default
            raw = row[0] if not hasattr(row, "keys") else row["valor"]
            return json.loads(raw or "null")
        except (json.JSONDecodeError, sqlite3.Error, TypeError):
            return default
        finally:
            connection.close()

    def _save_json_setting(self, key: str, value: Any) -> None:
        connection = self.connection_factory()
        try:
            if not self._table_exists(connection, "configuracoes"):
                raise RuntimeError("Tabela configuracoes não disponível.")
            connection.execute("INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)", (key, json.dumps(value, ensure_ascii=False, sort_keys=True)))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _audit(self, actor: str, action: str, object_id: str, details: str) -> None:
        if self.audit:
            self.audit("relatorios", action, object_id, details, "SUCESSO", actor)

    @staticmethod
    def _normalize_date(value: str, *, end: bool) -> str | None:
        value = str(value or "").strip()
        if not value:
            return None
        parsed = None
        for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(value, pattern)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError("Data inválida. Use DD/MM/AAAA.")
        return parsed.strftime("%Y-%m-%d") + (" 23:59:59" if end else " 00:00:00")

    @staticmethod
    def _date_where(column: str | None, start: str | None, end: str | None) -> tuple[list[str], list[Any]]:
        where: list[str] = []
        params: list[Any] = []
        expression = ReportService._normalized_date_expression(column) if column else ""
        if column and start:
            where.append(f"{expression}>=?")
            params.append(start)
        if column and end:
            where.append(f"{expression}<=?")
            params.append(end)
        return where, params

    @staticmethod
    def _normalized_date_expression(column: str) -> str:
        """Compara datas ISO e o formato histórico DD/MM/AAAA sem alterar dados."""
        return (
            f"(CASE WHEN substr({column},3,1)='/' AND substr({column},6,1)='/' "
            f"THEN substr({column},7,4)||'-'||substr({column},4,2)||'-'||"
            f"substr({column},1,2)||substr({column},11) ELSE {column} END)"
        )

    _table_exists = staticmethod(table_exists)

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}

    @staticmethod
    def _first(columns: Iterable[str], *names: str) -> str | None:
        values = set(columns)
        return next((name for name in names if name in values), None)
