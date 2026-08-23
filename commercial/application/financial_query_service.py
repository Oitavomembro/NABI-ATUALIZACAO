from __future__ import annotations

from datetime import date

from .ports import FinancialReadPort


class FinancialQueryService:
    """Fachada somente-leitura; não conhece SQL nem serviços do backend."""

    def __init__(self, gateway: FinancialReadPort) -> None:
        self._gateway = gateway

    def receivables(self, **filters):
        return self._gateway.receivables(**filters)

    def payables(self, **filters):
        return self._gateway.payables(**filters)

    def overdue_receivables(self, *, customer_id: int | None = None):
        return self._gateway.receivables(overdue=True, customer_id=customer_id)

    def upcoming_receivables(self, *, through: date, customer_id: int | None = None):
        return self._gateway.receivables(open_only=True, due_from=date.today(), due_to=through, customer_id=customer_id)

    def upcoming_payables(self, *, through: date):
        return self._gateway.payables(open_only=True, due_from=date.today(), due_to=through)

    def customer_collections(self, customer_id: int | None = None):
        return self._gateway.customer_collections(customer_id)

    def financial_summary(self, start_date: date, end_date: date):
        return self._gateway.financial_summary(start_date, end_date)

    def cash_flow(self, start_date: date, end_date: date):
        return self._gateway.cash_flow(start_date, end_date)
