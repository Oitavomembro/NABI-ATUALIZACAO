from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from contextlib import closing
from typing import Callable, Iterable

from database.maintenance import DatabaseMaintenanceService


@dataclass(frozen=True)
class FactoryResetPlan:
    mode: str
    title: str
    description: str
    requires_typed_confirmation: bool
    affected_tables: tuple[str, ...]
    row_counts: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())


class FactoryResetService:
    """Planeja e executa restaurações destrutivas com backup validado obrigatório."""

    MODES = {
        "APPEARANCE": ("Somente aparência", "Restaura tema e cor de destaque; preserva dados e demais preferências.", False),
        "PERSONALIZATION": ("Personalizações", "Restaura aparência, interface, favoritos e atalhos; preserva dados.", False),
        "SETTINGS": ("Configurações gerais", "Restaura configurações gerais e de impressão; preserva dados operacionais.", False),
        "TEST_DATA": ("Limpar dados de teste", "Remove cadastros identificados explicitamente como TESTE e seus vínculos.", True),
        "OPERATIONAL_DATA": ("Apagar cadastros e movimentações", "Remove cadastros, estoque, vendas, financeiro, compras e XML; preserva configurações e auditoria.", True),
        "COMPLETE": ("Restauração completa", "Remove todos os dados de negócio e configurações persistidas, preservando apenas a estrutura do banco.", True),
    }

    OPERATIONAL_TABLES = (
        "pagamentos_titulos", "titulos_financeiros", "recebimento_compra_itens", "recebimentos_compra",
        "pedido_compra_itens", "pedidos_compra", "nfe_devolucao_itens", "nfe_devolucoes",
        "nfe_documentos_origem_itens", "nfe_documentos_origem", "nfe_importacoes", "produto_fornecedores",
        "estoque_movimentacoes", "historico_precos_produtos", "parcelas", "movimentacoes",
        "historico_clientes", "contatos_cobranca", "lembretes_promissorias", "produtos", "clientes",
        "fornecedores", "marcas_produtos", "categorias_produtos", "unidades_medida", "caixa_aberturas",
        "fechamentos_caixa", "documentos_emitidos",
    )
    # Metadados de migração pertencem ao estado estrutural do banco e nunca devem ser
    # apagados por uma restauração de dados. Sem eles, uma versão antiga pode tentar
    # reaplicar migrações já incorporadas ao schema.
    COMPLETE_EXTRA_TABLES = ("configuracoes", "log_acesso_admin", "auditoria")
    PROTECTED_SCHEMA_TABLES = ("schema_migrations", "log_migracao", "migracoes_execucoes")

    def __init__(self, database_path: str | Path, maintenance: DatabaseMaintenanceService):
        self.database_path = Path(database_path).resolve()
        self.maintenance = maintenance

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=60)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _existing_tables(connection: sqlite3.Connection) -> set[str]:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    @classmethod
    def _tables_for_mode(cls, connection: sqlite3.Connection, mode: str) -> tuple[str, ...]:
        existing = cls._existing_tables(connection)
        user_tables = {name for name in existing if not name.startswith("sqlite_")}
        if mode == "COMPLETE":
            # Restauração completa preserva somente metadados estruturais de migração.
            return tuple(sorted(user_tables.difference(cls.PROTECTED_SCHEMA_TABLES)))
        if mode == "OPERATIONAL_DATA":
            # Preserva configuração e auditoria, mas remove todos os dados de negócio,
            # inclusive tabelas legadas que não constavam da lista estática original.
            preserved = set(cls.PROTECTED_SCHEMA_TABLES).union(cls.COMPLETE_EXTRA_TABLES)
            return tuple(sorted(user_tables.difference(preserved)))
        return tuple(name for name in cls.OPERATIONAL_TABLES if name in user_tables)

    def plan(self, mode: str) -> FactoryResetPlan:
        normalized = mode.strip().upper()
        if normalized not in self.MODES:
            raise ValueError(f"Modo de restauração inválido: {mode}")
        title, description, typed = self.MODES[normalized]
        if normalized in {"APPEARANCE", "PERSONALIZATION", "SETTINGS"}:
            tables: tuple[str, ...] = ()
        elif normalized in {"COMPLETE", "OPERATIONAL_DATA"}:
            tables = ()
        else:
            tables = self.OPERATIONAL_TABLES
        counts: dict[str, int] = {}
        with closing(self._connect()) as connection:
            existing = self._existing_tables(connection)
            if normalized in {"COMPLETE", "OPERATIONAL_DATA"}:
                tables = self._tables_for_mode(connection, normalized)
            if normalized == "TEST_DATA":
                # A prévia deve mostrar apenas registros realmente elegíveis, e não
                # todas as linhas das tabelas operacionais.
                product_ids, client_ids = self._test_entity_ids(connection, existing)
                if "produtos" in existing:
                    counts["produtos"] = len(product_ids)
                if "clientes" in existing:
                    counts["clientes"] = len(client_ids)
                tables = tuple(name for name, count in counts.items() if count)
            else:
                for table in tables:
                    if table in existing:
                        counts[table] = int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        return FactoryResetPlan(normalized, title, description, typed, tuple(counts), counts)


    @staticmethod
    def _dependency_order(connection: sqlite3.Connection, tables: Iterable[str]) -> tuple[str, ...]:
        """Ordena tabelas filhas antes das tabelas pai para exclusões seguras."""
        selected = {str(name) for name in tables}
        parents: dict[str, set[str]] = {name: set() for name in selected}
        children: dict[str, set[str]] = {name: set() for name in selected}
        for child in selected:
            try:
                foreign_keys = connection.execute(f'PRAGMA foreign_key_list("{child}")').fetchall()
            except sqlite3.Error:
                foreign_keys = []
            for row in foreign_keys:
                parent = str(row[2])
                if parent in selected and parent != child:
                    parents[child].add(parent)
                    children[parent].add(child)

        # Folhas dependentes primeiro. Em ciclos, usa ordem estável e mantém FK OFF.
        ready = sorted(name for name in selected if not children[name])
        order: list[str] = []
        remaining = set(selected)
        while ready:
            current = ready.pop(0)
            if current not in remaining:
                continue
            order.append(current)
            remaining.remove(current)
            for parent in sorted(parents[current]):
                children[parent].discard(current)
                if parent in remaining and not children[parent]:
                    ready.append(parent)
                    ready.sort()
        order.extend(sorted(remaining))
        return tuple(order)

    def execute(
        self,
        mode: str,
        *,
        typed_confirmation: str = "",
        apply_configuration_reset: Callable[[str], None] | None = None,
    ) -> tuple[Path, FactoryResetPlan]:
        plan = self.plan(mode)
        if plan.requires_typed_confirmation and typed_confirmation.strip().upper() != "APAGAR TUDO":
            raise ValueError('Digite exatamente "APAGAR TUDO" para confirmar.')
        backup_path, _ = self.maintenance.create_backup(prefix=f"antes_fabrica_{plan.mode.lower()}", validate=True)
        if plan.mode in {"APPEARANCE", "PERSONALIZATION", "SETTINGS"}:
            if apply_configuration_reset is None:
                raise ValueError("Callback de restauração de configurações não informado.")
            try:
                apply_configuration_reset(plan.mode)
                report = self.maintenance.check()
                if not report.valid:
                    raise RuntimeError("O banco falhou na validação após restaurar as configurações.")
            except Exception:
                # O callback grava configurações no mesmo banco. Qualquer falha parcial
                # precisa restaurar a cópia anterior para tornar a operação reversível.
                self.maintenance.restore(backup_path)
                raise
            return backup_path, plan

        connection = sqlite3.connect(str(self.database_path), timeout=60)
        try:
            # As bases legadas possuem relações que não usam ON DELETE CASCADE.
            # A restauração apaga um conjunto fechado de tabelas e valida todas as
            # chaves antes do commit, evitando falha por ordem de exclusão.
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            existing = self._existing_tables(connection)
            if plan.mode == "TEST_DATA":
                self._delete_test_data(connection, existing)
            else:
                deletion_order = self._dependency_order(connection, plan.affected_tables)
                for table in deletion_order:
                    if table in existing:
                        connection.execute(f'DELETE FROM "{table}"')
                if "sqlite_sequence" in existing and plan.affected_tables:
                    placeholders = ",".join("?" for _ in plan.affected_tables)
                    connection.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})", plan.affected_tables)
            connection.execute("PRAGMA foreign_keys=ON")
            violations = list(connection.execute("PRAGMA foreign_key_check"))
            if violations:
                sample = "; ".join(str(tuple(row)) for row in violations[:5])
                raise RuntimeError(f"A restauração deixaria vínculos inválidos: {sample}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        report = self.maintenance.check()
        if not report.valid:
            self.maintenance.restore(backup_path)
            raise RuntimeError("Restauração revertida porque o banco falhou na validação final.")
        if apply_configuration_reset is not None:
            try:
                apply_configuration_reset(plan.mode)
            except Exception:
                self.maintenance.restore(backup_path)
                raise
        final_report = self.maintenance.check()
        if not final_report.valid:
            self.maintenance.restore(backup_path)
            raise RuntimeError("Restauração revertida porque o estado final ficou inconsistente.")
        return backup_path, plan

    @staticmethod
    def _test_entity_ids(connection: sqlite3.Connection, existing: Iterable[str]) -> tuple[list[int], list[int]]:
        existing = set(existing)
        product_ids: list[int] = []
        client_ids: list[int] = []
        if "produtos" in existing:
            cols = {row[1] for row in connection.execute("PRAGMA table_info(produtos)")}
            searchable = [name for name in ("nome", "codigo", "descricao") if name in cols]
            if searchable:
                where = " OR ".join(f'UPPER(COALESCE("{name}",\'\')) LIKE \'%TESTE%\'' for name in searchable)
                product_ids = [int(row[0]) for row in connection.execute(f"SELECT id FROM produtos WHERE {where}")]
        if "clientes" in existing:
            cols = {row[1] for row in connection.execute("PRAGMA table_info(clientes)")}
            searchable = [name for name in ("nome", "cpf", "observacoes") if name in cols]
            if searchable:
                where = " OR ".join(f'UPPER(COALESCE("{name}",\'\')) LIKE \'%TESTE%\'' for name in searchable)
                client_ids = [int(row[0]) for row in connection.execute(f"SELECT id FROM clientes WHERE {where}")]
        return product_ids, client_ids

    @staticmethod
    def _delete_where_ids(connection: sqlite3.Connection, existing: set[str], table: str, column: str, ids: list[int]) -> None:
        if not ids or table not in existing:
            return
        columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
        if column not in columns:
            return
        placeholders = ",".join("?" for _ in ids)
        connection.execute(f'DELETE FROM "{table}" WHERE "{column}" IN ({placeholders})', ids)

    @classmethod
    def _delete_test_data(cls, connection: sqlite3.Connection, existing: Iterable[str]) -> None:
        existing = set(existing)
        product_ids, client_ids = cls._test_entity_ids(connection, existing)

        for table, column in (
            ("produto_fornecedores", "produto_id"),
            ("estoque_movimentacoes", "produto_id"),
            ("historico_precos_produtos", "produto_id"),
            ("pedido_compra_itens", "produto_id"),
            ("recebimento_compra_itens", "produto_id"),
            ("nfe_documentos_origem_itens", "produto_id"),
            ("nfe_devolucao_itens", "produto_id"),
        ):
            cls._delete_where_ids(connection, existing, table, column, product_ids)
        for table, column in (
            ("historico_clientes", "cliente_id"),
            ("contatos_cobranca", "cliente_id"),
            ("lembretes_promissorias", "cliente_id"),
            ("parcelas", "cliente_id"),
            ("movimentacoes", "cliente_id"),
            ("titulos_financeiros", "pessoa_id"),
        ):
            cls._delete_where_ids(connection, existing, table, column, client_ids)

        cls._delete_where_ids(connection, existing, "produtos", "id", product_ids)
        cls._delete_where_ids(connection, existing, "clientes", "id", client_ids)
