from __future__ import annotations

from datetime import date

from commercial.domain.money import MoneyCodec

from .dto import CustomerRecord, ProductRecord
from .ports import CommercialReadPort, CustomerAccountPort, CustomerLookupPort, ProductLookupPort
from .query_dto import (
    CancelledSaleSummary, CustomerCreditSummary, DailyMovementSummary,
    DailySaleSummary, OverdueChargeSummary, ReceiptSummary,
)


class CommercialQueryService:
    """Fachada comercial somente leitura, sem conhecimento de persistência."""

    def __init__(
        self,
        *,
        customers: CustomerLookupPort,
        products: ProductLookupPort,
        reporting: CommercialReadPort,
        customer_accounts: CustomerAccountPort | None = None,
        product_application=None,
    ) -> None:
        self._customers = customers
        self._products = products
        self._reporting = reporting
        self._customer_accounts = customer_accounts
        self._product_application = product_application

    def _accounts(self) -> CustomerAccountPort:
        if self._customer_accounts is None:
            raise RuntimeError("Consultas da ficha do cliente não estão configuradas.")
        return self._customer_accounts

    def search_customers(self, term: str, *, limit: int = 30) -> tuple[CustomerRecord, ...]:
        return self._customers.search(term, limit=limit)

    def get_customer(self, customer_id: int) -> CustomerRecord | None:
        return self._customers.get(customer_id)

    def customer_credit(self, customer_id: int) -> CustomerCreditSummary:
        customer = self.get_customer(customer_id)
        if customer is None:
            raise ValueError("Cliente não encontrado.")
        limit = customer.credit_limit or MoneyCodec.ZERO
        balance = customer.debt_balance or MoneyCodec.ZERO
        return CustomerCreditSummary(
            customer_id=customer.customer_id,
            credit_limit=limit,
            debt_balance=balance,
            available_credit=max(MoneyCodec.ZERO, limit - balance),
        )

    def search_products(self, term: str, *, limit: int = 30) -> tuple[ProductRecord, ...]:
        return self._products.search(term, limit=limit)

    def get_product(self, product_id: int) -> ProductRecord | None:
        return self._products.get(product_id)

    def daily_sales(self, day: date) -> tuple[DailySaleSummary, ...]:
        return self._reporting.sales_for_day(day)

    def daily_receipts(self, day: date) -> tuple[ReceiptSummary, ...]:
        return self._reporting.receipts_for_day(day)

    def overdue_charges(self) -> tuple[OverdueChargeSummary, ...]:
        return self._reporting.overdue_charges()

    def cancelled_sales(self, day: date) -> tuple[CancelledSaleSummary, ...]:
        return self._reporting.cancelled_sales_for_day(day)

    def daily_movements(self, day: date) -> tuple[DailyMovementSummary, ...]:
        return self._reporting.movements_for_day(day)

    def customer_details(self, customer_id: int):
        details = self._accounts().details(customer_id)
        if details is None:
            raise ValueError("Cliente não encontrado.")
        return details

    def customer_statement(self, customer_id: int):
        return self._accounts().statement(customer_id)

    def customer_open_installments(self, customer_id: int):
        return self._accounts().open_installments(customer_id)

    def customer_receipts(self, customer_id: int):
        return self._accounts().receipts(customer_id)

    def _product_app(self):
        if self._product_application is None:
            raise RuntimeError("Consultas detalhadas de produto não estão configuradas.")
        return self._product_application

    def product_details(self, product_id: int):
        return self._product_app().get_product(product_id)

    def product_stock(self, product_id: int):
        return self._product_app().product_stock(product_id)

    def product_movements(self, product_id: int, *, limit: int = 200):
        return self._product_app().product_movements(product_id, limit=limit)

    def low_stock_products(self):
        return self._product_app().low_stock_products()
