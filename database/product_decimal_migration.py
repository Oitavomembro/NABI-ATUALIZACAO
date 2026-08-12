from __future__ import annotations

from database import DatabaseManager
from database.sqlite_introspection import table_exists


class ProductDecimalMigration:
    """Fonte única da migração idempotente das representações decimais."""

    TABLE_MAPPINGS = {
        "produtos": {
            "preco_venda_decimal": "preco_venda",
            "preco_custo_decimal": "preco_custo",
            "despesas_percentual_decimal": "despesas_percentual",
            "margem_lucro_decimal": "margem_lucro",
            "fator_conversao_decimal": "fator_conversao",
        },
        "historico_precos_produtos": {
            "preco_anterior_decimal": "preco_anterior",
            "preco_novo_decimal": "preco_novo",
            "custo_decimal": "custo",
            "margem_percentual_decimal": "margem_percentual",
        },
        "produto_fornecedores": {
            "fator_conversao_decimal": "fator_conversao",
            "ultimo_custo_decimal": "ultimo_custo",
        },
        "pedido_compra_itens": {
            "custo_unitario_decimal": "custo_unitario",
            "valor_total_decimal": "valor_total",
        },
        "recebimento_compra_itens": {
            "custo_unitario_decimal": "custo_unitario",
            "valor_total_decimal": "valor_total",
        },
        "titulos_financeiros": {
            "valor_original_decimal": "valor_original",
            "valor_pago_decimal": "valor_pago",
        },
        "pagamentos_titulos": {
            "valor_decimal": "valor",
        },
        "movimentacoes": {
            "valor_decimal": "valor",
            "valor_aberto_decimal": "valor_aberto",
        },
        "parcelas": {
            "valor_parcela_decimal": "valor_parcela",
            "valor_pago_decimal": "valor_pago",
        },
        "clientes": {
            "saldo_devedor_decimal": "saldo_devedor",
        },
        "caixa_aberturas": {
            "valor_inicial_decimal": "valor_inicial",
        },
        "fechamentos_caixa": {
            "valor_esperado_decimal": "valor_esperado",
            "valor_contado_decimal": "valor_contado",
            "diferenca_decimal": "diferenca",
        },
    }

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    @staticmethod
    def _columns(connection, table: str) -> set[str]:
        return {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}

    _table_exists = staticmethod(table_exists)

    @classmethod
    def _migrate_table(cls, connection, table: str, mapping: dict[str, str]) -> None:
        if not cls._table_exists(connection, table):
            return
        columns = cls._columns(connection, table)
        applicable = {target: source for target, source in mapping.items() if source in columns}
        for target in applicable:
            if target not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {target} TEXT")
                columns.add(target)
        assignments = [
            f"{target}=COALESCE(NULLIF(TRIM({target}), ''), CAST({source} AS TEXT))"
            for target, source in applicable.items()
        ]
        if assignments:
            connection.execute(f"UPDATE {table} SET {', '.join(assignments)}")

    @classmethod
    def migrate_connection(cls, connection) -> None:
        if not cls._table_exists(connection, "produtos"):
            raise RuntimeError("A tabela produtos não existe; inicialize o schema antes da migração decimal.")
        for table, mapping in cls.TABLE_MAPPINGS.items():
            cls._migrate_table(connection, table, mapping)

    def run(self) -> None:
        with self.database.session(write=True) as connection:
            self.migrate_connection(connection)
