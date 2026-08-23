from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .money import MoneyCodec, MoneyValueError


class PaymentMethod(str, Enum):
    CASH = "DINHEIRO"
    PIX = "PIX"
    DEBIT = "DEBITO"
    CREDIT_CARD = "CREDITO"
    STORE_CREDIT = "CREDIARIO"
    OTHER = "OUTROS"


@dataclass(frozen=True, slots=True)
class Payment:
    method: PaymentMethod
    amount: Decimal
    card_authorization: str = ""

    def __post_init__(self) -> None:
        try:
            method = self.method if isinstance(self.method, PaymentMethod) else PaymentMethod(str(self.method).strip().upper())
        except ValueError as exc:
            raise ValueError("Forma de pagamento inválida.") from exc
        try:
            amount = MoneyCodec.parse(self.amount, field="valor do pagamento")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        if amount <= 0:
            raise ValueError("Cada pagamento deve ser maior que zero.")
        authorization = str(self.card_authorization or "").strip()
        if len(authorization) > 20:
            raise ValueError("A autorização do cartão deve possuir no máximo 20 caracteres.")
        if authorization and method not in {PaymentMethod.DEBIT, PaymentMethod.CREDIT_CARD}:
            raise ValueError("Autorização só pode ser informada para cartão.")
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "card_authorization", authorization)


@dataclass(frozen=True, slots=True)
class PaymentValidation:
    sale_total: Decimal
    received: Decimal
    change: Decimal
    financed_value: Decimal


@dataclass(frozen=True, slots=True)
class PaymentPlan:
    payments: tuple[Payment, ...]

    def __init__(self, payments: Iterable[Payment]) -> None:
        normalized = tuple(payments)
        if any(not isinstance(payment, Payment) for payment in normalized):
            raise TypeError("PaymentPlan aceita somente pagamentos válidos.")
        object.__setattr__(self, "payments", normalized)

    @property
    def total(self) -> Decimal:
        return sum((payment.amount for payment in self.payments), MoneyCodec.ZERO)

    @property
    def financed_value(self) -> Decimal:
        return sum(
            (
                payment.amount
                for payment in self.payments
                if payment.method is PaymentMethod.STORE_CREDIT
            ),
            MoneyCodec.ZERO,
        )

    @property
    def has_store_credit(self) -> bool:
        return self.financed_value > 0

    def entrance_value(self, sale_total: Decimal | int | str) -> Decimal:
        total = MoneyCodec.parse(sale_total, field="total da venda")
        return (total - self.financed_value).quantize(MoneyCodec.CENT)

    def validate_against(self, sale_total: Decimal | int | str) -> PaymentValidation:
        total = MoneyCodec.parse(sale_total, field="total da venda")
        if total <= 0:
            raise ValueError("O total da venda deve ser maior que zero.")
        if not self.payments:
            raise ValueError("Informe ao menos uma forma de pagamento.")

        store_credit = [
            payment for payment in self.payments
            if payment.method is PaymentMethod.STORE_CREDIT
        ]
        if len(store_credit) > 1:
            raise ValueError("Informe somente uma parte em crediário.")
        if store_credit:
            if self.total != total:
                raise ValueError(
                    "A entrada somada ao valor financiado deve ser igual ao total da venda."
                )
            return PaymentValidation(total, total, MoneyCodec.ZERO, self.financed_value)

        cash = sum(
            (payment.amount for payment in self.payments if payment.method is PaymentMethod.CASH),
            MoneyCodec.ZERO,
        )
        non_cash = self.total - cash
        if self.total < total:
            raise ValueError("Os pagamentos não atingem o total da venda.")
        if non_cash > total:
            raise ValueError("Pagamentos sem dinheiro não podem gerar troco.")
        cash_applied = max(MoneyCodec.ZERO, total - non_cash)
        change = max(MoneyCodec.ZERO, cash - cash_applied).quantize(MoneyCodec.CENT)
        if self.total > total and change <= 0:
            raise ValueError("Pagamento excedente só é permitido quando há dinheiro para o troco.")
        return PaymentValidation(total, self.total, change, MoneyCodec.ZERO)
