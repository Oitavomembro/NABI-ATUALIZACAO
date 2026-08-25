from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from commercial.domain.money import MoneyCodec
from .action_dto import ActionContext, ActionSensitivity


def _money(value, field_name: str) -> Decimal:
    return MoneyCodec.parse(value, field=field_name)


@dataclass(frozen=True, slots=True)
class ReceivableSummary:
    title_id: int
    customer_id: int | None
    customer_name: str
    origin: str
    origin_id: str
    document: str
    description: str
    original_amount: Decimal
    received_amount: Decimal
    open_amount: Decimal
    issue_date: date
    due_date: date
    status: str
    overdue: bool

    def __post_init__(self) -> None:
        for name in ("original_amount", "received_amount", "open_amount"):
            object.__setattr__(self, name, _money(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class PayableSummary:
    title_id: int
    beneficiary_id: int | None
    beneficiary_name: str
    origin: str
    origin_id: str
    document: str
    description: str
    original_amount: Decimal
    paid_amount: Decimal
    open_amount: Decimal
    issue_date: date
    due_date: date
    status: str
    overdue: bool
    cost_center: str = ""

    def __post_init__(self) -> None:
        for name in ("original_amount", "paid_amount", "open_amount"):
            object.__setattr__(self, name, _money(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class CustomerCollectionSummary:
    installment_id: int
    customer_id: int
    customer_name: str
    phone: str
    installment_number: int
    open_amount: Decimal
    due_date: date
    overdue_days: int
    last_contact: str
    situation: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "open_amount", _money(self.open_amount, "saldo em cobrança"))


@dataclass(frozen=True, slots=True)
class FinancialSummary:
    receivable_open: Decimal
    receivable_overdue: Decimal
    payable_open: Decimal
    payable_due_today: Decimal
    received_in_period: Decimal
    paid_in_period: Decimal

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, _money(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class FinancialTitlePage:
    items: tuple[ReceivableSummary | PayableSummary, ...]
    total_records: int
    limit: int
    offset: int

    def __post_init__(self) -> None:
        if self.total_records < 0 or self.limit < 1 or self.offset < 0:
            raise ValueError("Página financeira inválida.")
        if len(self.items) > self.limit:
            raise ValueError("A página financeira excede o limite solicitado.")


@dataclass(frozen=True, slots=True)
class CashFlowEntry:
    payment_id: int
    title_id: int
    occurred_at: datetime
    direction: str
    amount: Decimal
    origin: str
    description: str
    reference: str

    def __post_init__(self) -> None:
        if self.direction not in {"ENTRADA", "SAIDA"}:
            raise ValueError("Direção do fluxo deve ser ENTRADA ou SAIDA.")
        object.__setattr__(self, "amount", _money(self.amount, "valor do fluxo"))


@dataclass(frozen=True, slots=True)
class CreateFinancialTitleCommand:
    amount: Decimal
    due_date: date
    party_id: int | None = None
    party_name: str = ""
    document: str = ""
    description: str = ""
    notes: str = ""
    issue_date: date | None = None

    def __post_init__(self) -> None:
        amount = _money(self.amount, "valor do título")
        if amount <= 0:
            raise ValueError("O valor do título deve ser maior que zero.")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class SettleFinancialTitleCommand:
    title_id: int
    amount: Decimal
    payment_method: str
    payment_date: date
    notes: str = ""

    def __post_init__(self) -> None:
        amount = _money(self.amount, "valor da baixa")
        method = str(self.payment_method or "").strip().upper()
        if int(self.title_id) <= 0 or amount <= 0 or not method:
            raise ValueError("Título, valor e forma de pagamento são obrigatórios.")
        object.__setattr__(self, "title_id", int(self.title_id))
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "payment_method", method)


@dataclass(frozen=True, slots=True)
class PersistedFinancialAction:
    title_id: int
    status: str
    open_amount: Decimal
    payment_id: int | None = None
    idempotent_replay: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "open_amount", _money(self.open_amount, "saldo do título"))


@dataclass(frozen=True, slots=True)
class FinancialActionResult:
    action: str
    context: ActionContext
    sensitivity: ActionSensitivity
    requires_human_confirmation: bool
    executed: bool
    committed: bool
    message: str
    title_id: int | None = None
    payment_id: int | None = None
    status: str = ""
    open_amount: Decimal | None = None
    secondary_effect_failed: bool = False


@dataclass(frozen=True, slots=True)
class FinancialEvent:
    kind: str
    title_id: int
    context: ActionContext
    payment_id: int | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
