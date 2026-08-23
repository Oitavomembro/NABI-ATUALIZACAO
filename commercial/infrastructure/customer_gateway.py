from __future__ import annotations

from decimal import Decimal

from commercial.application.dto import CustomerRecord


class NabiCodeCustomerGateway:
    """Adapta ClienteRepository sem expor banco ou linhas SQLite à aplicação."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def list(self, term: str = "", *, limit: int = 250) -> tuple[CustomerRecord, ...]:
        page = self.repository.list_page(term, page=0, per_page=limit)
        return tuple(
            CustomerRecord(
                customer_id=int(row[0]), code="", name=str(row[2] or ""),
                record_number=int(row[1]) if row[1] not in (None, "") else None,
                debt_balance=Decimal(str(row[3] or 0)),
                credit_limit=Decimal(str(row[4] or 0)),
            )
            for row in page.rows
        )

    def search(self, term: str, *, limit: int = 30) -> tuple[CustomerRecord, ...]:
        return tuple(
            CustomerRecord(
                customer_id=item.id,
                code=item.codigo,
                name=item.nome,
                record_number=item.numero_ficha,
            )
            for item in self.repository.search_sales_suggestions(term, limit=limit)
        )

    def get(self, customer_id: int) -> CustomerRecord | None:
        normalized_id = int(customer_id)
        if normalized_id <= 0:
            return None
        row = self.repository.database.fetch_one(
            """SELECT id, codigo, nome, numero_ficha, limite, saldo_devedor
                 FROM clientes
                WHERE id = ?""",
            (normalized_id,),
        )
        if row is None:
            return None
        return CustomerRecord(
            customer_id=int(row[0]),
            code=str(row[1] or ""),
            name=str(row[2] or ""),
            record_number=int(row[3]) if row[3] not in (None, "") else None,
            credit_limit=Decimal(str(row[4] or 0)),
            debt_balance=Decimal(str(row[5] or 0)),
        )

    def get_final_consumer(self) -> CustomerRecord:
        customer_id = self.repository.get_or_create_final_consumer()
        customer = self.get(customer_id)
        if customer is None:
            raise ValueError("Consumidor Final não pôde ser localizado.")
        return customer
