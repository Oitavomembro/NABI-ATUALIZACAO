from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from commercial.domain.money import MoneyCodec


def _money(value: Decimal, field: str) -> Decimal:
    parsed = MoneyCodec.parse(value, field=field)
    if parsed < 0:
        raise ValueError(f"{field} não pode ser negativo.")
    return parsed


@dataclass(frozen=True, slots=True)
class CustomerCreditSummary:
    customer_id: int
    credit_limit: Decimal
    debt_balance: Decimal
    available_credit: Decimal

    def __post_init__(self) -> None:
        limit = _money(self.credit_limit, "limite")
        balance = _money(self.debt_balance, "saldo devedor")
        available = _money(self.available_credit, "crédito disponível")
        expected = max(MoneyCodec.ZERO, limit - balance)
        if available != expected:
            raise ValueError("Crédito disponível inconsistente.")
        object.__setattr__(self, "customer_id", int(self.customer_id))
        object.__setattr__(self, "credit_limit", limit)
        object.__setattr__(self, "debt_balance", balance)
        object.__setattr__(self, "available_credit", available)


@dataclass(frozen=True, slots=True)
class DailySaleSummary:
    sale_id: int
    customer_id: int | None
    description: str
    total: Decimal
    occurred_at: str
    status: str
    cancelled: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "total", _money(self.total, "total da venda"))


@dataclass(frozen=True, slots=True)
class ReceiptSummary:
    payment_id: int
    title_id: int
    amount: Decimal
    payment_method: str
    paid_at: str
    customer_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _money(self.amount, "valor recebido"))


@dataclass(frozen=True, slots=True)
class OverdueChargeSummary:
    installment_id: int
    customer_id: int
    customer_name: str
    installment_number: int
    open_amount: Decimal
    due_date: date

    def __post_init__(self) -> None:
        object.__setattr__(self, "open_amount", _money(self.open_amount, "valor vencido"))


@dataclass(frozen=True, slots=True)
class CancelledSaleSummary:
    sale_id: int
    customer_id: int | None
    description: str
    total: Decimal
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "total", _money(self.total, "total cancelado"))


@dataclass(frozen=True, slots=True)
class DailyMovementSummary:
    movement_id: int
    occurred_at: str
    customer_name: str
    movement_type: str
    description: str
    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", MoneyCodec.parse(self.amount, field="movimentação"))


@dataclass(frozen=True, slots=True)
class QueryPeriod:
    day: date

    @classmethod
    def today(cls) -> "QueryPeriod":
        return cls(datetime.now().date())
