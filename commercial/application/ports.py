from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from .action_dto import ActionContext, PersistedCancellation, SaleCancelled
from .dto import CheckoutCommand, CheckoutReceipt, CheckoutResult, CustomerRecord, ProductRecord
from .query_dto import (
    CancelledSaleSummary, DailyMovementSummary, DailySaleSummary,
    OverdueChargeSummary, ReceiptSummary,
)
from .customer_dto import (
    CustomerDetails, CustomerInstallment, CustomerReceiptCommand,
    CustomerReceiptSummary, CustomerStatement, PersistedCustomerReceipt,
)
from .financial_dto import (
    CashFlowEntry, CreateFinancialTitleCommand, CustomerCollectionSummary,
    FinancialSummary, PayableSummary, PersistedFinancialAction,
    ReceivableSummary, SettleFinancialTitleCommand,
)
from .product_dto import (
    LowStockProductSummary, PersistedStockAction, ProductCreateCommand,
    ProductDetails, ProductStockSummary, ProductUpdateCommand,
    StockAdjustmentCommand, StockMovementCommand, StockMovementSummary,
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

    def get_final_consumer(self) -> CustomerRecord: ...


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
class SaleReceiptOutputPort(Protocol):
    """Saídas explícitas de comprovante, disponíveis somente após o commit."""

    def print_thermal(self, receipt: CheckoutReceipt) -> str: ...

    def generate_pdf(self, receipt: CheckoutReceipt) -> str: ...

    def open_file(self, path: str) -> str: ...


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


@runtime_checkable
class FinancialReadPort(Protocol):
    def receivables(self, **filters) -> tuple[ReceivableSummary, ...]: ...
    def payables(self, **filters) -> tuple[PayableSummary, ...]: ...
    def customer_collections(self, customer_id: int | None = None) -> tuple[CustomerCollectionSummary, ...]: ...
    def financial_summary(self, start_date, end_date) -> FinancialSummary: ...
    def cash_flow(self, start_date, end_date) -> tuple[CashFlowEntry, ...]: ...


@runtime_checkable
class FinancialActionPort(Protocol):
    def create_title(self, title_type: str, command: CreateFinancialTitleCommand, *, user: str) -> PersistedFinancialAction: ...
    def settle(self, title_type: str, command: SettleFinancialTitleCommand, *, user: str) -> PersistedFinancialAction: ...
    def cancel(self, title_id: int, *, user: str) -> PersistedFinancialAction: ...
    def reverse_payment(self, payment_id: int, *, user: str) -> PersistedFinancialAction: ...


@runtime_checkable
class FinancialEventPort(Protocol):
    def financial_event(self, event) -> None: ...


@runtime_checkable
class ProductCatalogPort(Protocol):
    def create(self, command: ProductCreateCommand) -> ProductDetails: ...
    def update(self, command: ProductUpdateCommand) -> ProductDetails: ...
    def get_details(self, product_id: int) -> ProductDetails | None: ...
    def search_details(self, term: str, *, limit: int = 30) -> tuple[ProductDetails, ...]: ...
    def get_by_barcode(self, barcode: str) -> ProductDetails | None: ...


@runtime_checkable
class StockReadPort(Protocol):
    def stock(self, product_id: int) -> ProductStockSummary: ...
    def movements(self, product_id: int, *, limit: int = 200) -> tuple[StockMovementSummary, ...]: ...
    def low_stock(self) -> tuple[LowStockProductSummary, ...]: ...


@runtime_checkable
class StockActionPort(Protocol):
    def receive(self, command: StockMovementCommand, *, user: str) -> PersistedStockAction: ...
    def remove(self, command: StockMovementCommand, *, user: str) -> PersistedStockAction: ...
    def adjust(self, command: StockAdjustmentCommand, *, user: str) -> PersistedStockAction: ...


@runtime_checkable
class StockEventPort(Protocol):
    def stock_event(self, event) -> None: ...
