from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from database import DatabaseManager


class CustomerMaintenanceRepository:
    """Persistência administrativa de clientes, sem regras de apresentação."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def delete_fictitious(self) -> int:
        """Remove clientes fictícios e vínculos relacionados em uma transação."""
        with self.database.session(write=True) as connection:
            fictitious_rows = connection.execute(
                "SELECT id FROM clientes WHERE COALESCE(ficticio, 0) = 1"
            ).fetchall()
            customer_ids = [int(row[0]) for row in fictitious_rows]
            customer_count = len(customer_ids)
            if not customer_count:
                return 0
            placeholders = ",".join("?" for _ in customer_ids)

            movement_rows = connection.execute(
                f"SELECT id FROM movimentacoes WHERE cliente_id IN ({placeholders})",
                tuple(customer_ids),
            ).fetchall()
            movement_ids = [int(row[0]) for row in movement_rows]
            if movement_ids:
                movement_placeholders = ",".join("?" for _ in movement_ids)
                connection.execute(
                    f"DELETE FROM parcelas WHERE movimentacao_id IN ({movement_placeholders})",
                    tuple(movement_ids),
                )

            connection.execute(
                f"DELETE FROM movimentacoes WHERE cliente_id IN ({placeholders})",
                tuple(customer_ids),
            )
            connection.execute(
                f"DELETE FROM historico_clientes WHERE cliente_id IN ({placeholders})",
                tuple(customer_ids),
            )
            connection.execute(
                f"DELETE FROM clientes WHERE id IN ({placeholders})",
                tuple(customer_ids),
            )
            return customer_count

    def create_missing_demo_customers(self, customers: Iterable[Sequence[Any]]) -> int:
        """Insere apenas demonstrações ainda inexistentes, sem consulta por item."""
        candidates = [tuple(customer) for customer in customers]
        if not candidates:
            return 0

        with self.database.session(write=True) as connection:
            existing_rows = connection.execute(
                "SELECT codigo, numero_ficha FROM clientes"
            ).fetchall()
            existing_codes = {str(row[0]) for row in existing_rows if row[0] is not None}
            existing_records = {int(row[1]) for row in existing_rows if row[1] is not None}

            missing = []
            for customer in candidates:
                code, record_number = str(customer[0]), int(customer[1])
                if code in existing_codes or record_number in existing_records:
                    continue
                missing.append(customer)
                existing_codes.add(code)
                existing_records.add(record_number)

            if not missing:
                return 0

            connection.executemany(
                """
                INSERT INTO clientes (
                    codigo, numero_ficha, nome, cpf, rg, telefone, endereco,
                    observacoes, limite, saldo_devedor, ficticio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                missing,
            )
            return len(missing)

    def export_rows(self) -> list[tuple[Any, ...]]:
        rows = self.database.fetch_all(
            """
            SELECT numero_ficha, codigo, nome, cpf, rg, telefone, endereco,
                   limite, saldo_devedor, observacoes
            FROM clientes
            ORDER BY nome COLLATE NOCASE
            """
        )
        return [tuple(row) for row in rows]
