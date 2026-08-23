from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from commercial.domain.money import MoneyCodec


@dataclass(frozen=True, slots=True)
class CustomerCreateCommand:
    name: str
    code: str = ""
    record_number: int | None = None
    cpf: str = ""
    rg: str = ""
    phone: str = ""
    address: str = ""
    notes: str = ""
    credit_limit: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        object.__setattr__(self, "credit_limit", MoneyCodec.parse(self.credit_limit, field="limite"))


@dataclass(frozen=True, slots=True)
class CustomerUpdateCommand:
    customer_id: int
    name: str
    code: str = ""
    record_number: int | None = None
    cpf: str = ""
    rg: str = ""
    phone: str = ""
    address: str = ""
    notes: str = ""
    credit_limit: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        if int(self.customer_id) <= 0:
            raise ValueError("Cliente inválido.")
        object.__setattr__(self, "customer_id", int(self.customer_id))
        object.__setattr__(self, "credit_limit", MoneyCodec.parse(self.credit_limit, field="limite"))


@dataclass(frozen=True, slots=True)
class CustomerDetails:
    customer_id: int
    code: str
    record_number: int | None
    name: str
    cpf: str
    rg: str
    phone: str
    address: str
    notes: str
    credit_limit: Decimal
    debt_balance: Decimal
    available_credit: Decimal

    def __post_init__(self) -> None:
        limit = MoneyCodec.parse(self.credit_limit, field="limite")
        balance = MoneyCodec.parse(self.debt_balance, field="saldo devedor")
        available = MoneyCodec.parse(self.available_credit, field="crédito disponível")
        if available != max(MoneyCodec.ZERO, limit - balance):
            raise ValueError("Crédito disponível inconsistente.")
        object.__setattr__(self, "credit_limit", limit)
        object.__setattr__(self, "debt_balance", balance)
        object.__setattr__(self, "available_credit", available)


@dataclass(frozen=True, slots=True)
class CustomerStatementEntry:
    movement_id: int
    occurred_at: str
    movement_type: str
    description: str
    reference: str
    debit: Decimal
    credit: Decimal
    financial_effect: Decimal
    status: str

    def __post_init__(self) -> None:
        for field_name in ("debit", "credit", "financial_effect"):
            object.__setattr__(self, field_name, MoneyCodec.parse(getattr(self, field_name), field=field_name))


@dataclass(frozen=True, slots=True)
class CustomerInstallment:
    installment_id: int
    sale_id: int
    number: int
    amount: Decimal
    paid_amount: Decimal
    open_amount: Decimal
    due_date: date | None
    status: str
    overdue: bool

    def __post_init__(self) -> None:
        for field_name in ("amount", "paid_amount", "open_amount"):
            object.__setattr__(self, field_name, MoneyCodec.parse(getattr(self, field_name), field=field_name))


@dataclass(frozen=True, slots=True)
class CustomerReceiptSummary:
    movement_id: int
    occurred_at: str
    amount: Decimal
    payment_method: str
    description: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", MoneyCodec.parse(self.amount, field="recebimento"))


@dataclass(frozen=True, slots=True)
class CustomerStatement:
    customer: CustomerDetails
    entries: tuple[CustomerStatementEntry, ...]
    installments: tuple[CustomerInstallment, ...]
    receipts: tuple[CustomerReceiptSummary, ...]
    pending_amount: Decimal
    overdue_amount: Decimal
    historical_running_balance_available: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "pending_amount", MoneyCodec.parse(self.pending_amount, field="pendente"))
        object.__setattr__(self, "overdue_amount", MoneyCodec.parse(self.overdue_amount, field="vencido"))


@dataclass(frozen=True, slots=True)
class CustomerReceiptCommand:
    customer_id: int
    amount: Decimal
    payment_method: str
    payment_date: date
    notes: str = ""

    def __post_init__(self) -> None:
        amount = MoneyCodec.parse(self.amount, field="valor recebido")
        if int(self.customer_id) <= 0 or amount <= 0:
            raise ValueError("Cliente e valor do recebimento devem ser válidos.")
        method = str(self.payment_method or "").strip().upper()
        if not method:
            raise ValueError("Forma de pagamento obrigatória.")
        object.__setattr__(self, "customer_id", int(self.customer_id))
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "payment_method", method)


@dataclass(frozen=True, slots=True)
class PersistedCustomerReceipt:
    movement_id: int
    customer_id: int
    amount: Decimal
    previous_balance: Decimal
    new_balance: Decimal
    payment_method: str


@dataclass(frozen=True, slots=True)
class CustomerPaymentReceived:
    receipt: PersistedCustomerReceipt
    request_id: str
    requested_by: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
