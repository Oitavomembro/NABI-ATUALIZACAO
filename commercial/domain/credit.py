from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from .money import MoneyCodec, MoneyValueError


@dataclass(frozen=True, slots=True)
class CreditInstallment:
    number: int
    due_date: date
    amount: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.number, bool) or int(self.number) <= 0:
            raise ValueError("O número da parcela deve ser positivo.")
        if not isinstance(self.due_date, date):
            raise TypeError("O vencimento deve ser uma data.")
        try:
            amount = MoneyCodec.parse(self.amount, field="valor da parcela")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        if amount <= 0:
            raise ValueError("O valor da parcela deve ser maior que zero.")
        object.__setattr__(self, "number", int(self.number))
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class CreditTerms:
    down_payment: Decimal
    financed_value: Decimal
    installments: tuple[CreditInstallment, ...]

    def __post_init__(self) -> None:
        try:
            down_payment = MoneyCodec.parse(self.down_payment, field="entrada")
            financed = MoneyCodec.parse(self.financed_value, field="valor financiado")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        if down_payment < 0:
            raise ValueError("A entrada não pode ser negativa.")
        if financed <= 0:
            raise ValueError("O valor financiado deve ser maior que zero.")
        installments = tuple(self.installments)
        if not installments:
            raise ValueError("Informe ao menos uma parcela.")
        if any(not isinstance(item, CreditInstallment) for item in installments):
            raise TypeError("Parcelas inválidas.")
        if tuple(item.number for item in installments) != tuple(range(1, len(installments) + 1)):
            raise ValueError("A numeração das parcelas deve ser contínua a partir de 1.")
        due_dates = tuple(item.due_date for item in installments)
        if any(current <= previous for previous, current in zip(due_dates, due_dates[1:])):
            raise ValueError("Os vencimentos devem estar em ordem crescente.")
        installment_total = sum((item.amount for item in installments), MoneyCodec.ZERO)
        if installment_total != financed:
            raise ValueError("A soma das parcelas deve ser igual ao valor financiado.")
        object.__setattr__(self, "down_payment", down_payment)
        object.__setattr__(self, "financed_value", financed)
        object.__setattr__(self, "installments", installments)

    @property
    def installment_count(self) -> int:
        return len(self.installments)

    @classmethod
    def create(
        cls,
        *,
        down_payment: Decimal | int | str,
        financed_value: Decimal | int | str,
        due_dates: Iterable[date],
    ) -> "CreditTerms":
        financed = MoneyCodec.parse(financed_value, field="valor financiado")
        dates = tuple(due_dates)
        if not dates:
            raise ValueError("Informe ao menos um vencimento.")
        total_cents = int(financed / MoneyCodec.CENT)
        if financed <= 0 or len(dates) > total_cents:
            raise ValueError("O valor financiado não comporta a quantidade de parcelas.")
        base_cents, residual_cents = divmod(total_cents, len(dates))
        installments = tuple(
            CreditInstallment(
                number=index + 1,
                due_date=due_date,
                amount=MoneyCodec.CENT * (base_cents + (1 if index < residual_cents else 0)),
            )
            for index, due_date in enumerate(dates)
        )
        return cls(
            down_payment=down_payment,
            financed_value=financed,
            installments=installments,
        )
