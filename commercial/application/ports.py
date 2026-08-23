from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from .action_dto import ActionContext, PersistedCancellation, SaleCancelled
from .dto import CheckoutCommand, CheckoutResult, CustomerRecord, ProductRecord
from .query_dto import (
    CancelledSaleSummary, DailyMovementSummary, DailySaleSummary,
    OverdueChargeSummary, ReceiptSummary,
)
from .customer_dto import (
    CustomerDetails, CustomerInstallment, CustomerReceiptCommand,
    CustomerReceiptSummary, CustomerStatement, PersistedCustomerReceipt,
)


@dataclass(frozen=True, slots=True)
class PersistedCheckout:
    sale_id: int
    total: Decimal
    received: Decimal
    change: Decimal
    payment_description: str
    status: str


@runtime_checkable
class CustomerLookupPort(Protocol):
    def search(self, term: str, *, limit: int = 30) -> tuple[CustomerRecord, ...]: ...

    def get(self, customer_id: int) -> CustomerRecord | None: ...


@runtime_checkable
class ProductLookupPort(Protocol):
    def search(self, term: str, *, limit: int = 30) -> tuple[ProductRecord, ...]: ...

    def get(self, product_id: int) -> ProductRecord | None: ...


@runtime_checkable
class CheckoutPort(Protocol):
    """Retorno significa commit confirmado; exceção significa rollback/pré-commit."""

    def checkout(
        self,
        command: CheckoutCommand,
        *,
        customer: CustomerRecord,
        user: str,
    ) -> PersistedCheckout: ...


@runtime_checkable
class CommercialEventPort(Protocol):
    """Efeito secundário executado somente depois do commit da venda."""

    def sale_committed(self, result: CheckoutResult) -> None: ...


@runtime_checkable
class CommercialReadPort(Protocol):
    def sales_for_day(self, day) -> tuple[DailySaleSummary, ...]: ...
    def receipts_for_day(self, day) -> tuple[ReceiptSummary, ...]: ...
    def overdue_charges(self) -> tuple[OverdueChargeSummary, ...]: ...
    def cancelled_sales_for_day(self, day) -> tuple[CancelledSaleSummary, ...]: ...
    def movements_for_day(self, day) -> tuple[DailyMovementSummary, ...]: ...


@runtime_checkable
class SaleCancellationPort(Protocol):
    """Retorno significa que o cancelamento foi confirmado no banco."""

    def cancel(self, sale_id: int, *, user: str) -> PersistedCancellation: ...


@runtime_checkable
class CommercialActionEventPort(Protocol):
    def sale_cancelled(self, event: SaleCancelled) -> None: ...


@runtime_checkable
class CustomerAccountPort(Protocol):
    def details(self, customer_id: int) -> CustomerDetails | None: ...
    def statement(self, customer_id: int) -> CustomerStatement: ...
    def open_installments(self, customer_id: int) -> tuple[CustomerInstallment, ...]: ...
    def receipts(self, customer_id: int) -> tuple[CustomerReceiptSummary, ...]: ...


@runtime_checkable
class CustomerReceiptPort(Protocol):
    """Retorno significa recebimento confirmado integralmente na transação."""

    def receive(self, command: CustomerReceiptCommand, *, user: str) -> PersistedCustomerReceipt: ...
