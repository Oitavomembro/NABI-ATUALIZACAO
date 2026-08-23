from __future__ import annotations

from decimal import Decimal
from enum import Enum
from commercial.domain.cart import Cart, CartItem
from commercial.domain.credit import CreditTerms
from commercial.domain.money import MoneyCodec, MoneyValueError
from commercial.domain.payments import PaymentPlan

from .dto import CheckoutCommand


class CheckoutState(str, Enum):
    OPEN = "OPEN"
    CHECKING_OUT = "CHECKING_OUT"


class PDVSession:
    """Estado comercial transitório de uma única venda em preparação."""

    def __init__(self) -> None:
        self.cart = Cart()
        self.customer_id: int | None = None
        self.payment_plan: PaymentPlan | None = None
        self.credit_terms: CreditTerms | None = None
        self.discount_amount = MoneyCodec.ZERO
        self.surcharge_amount = MoneyCodec.ZERO
        self.checkout_state = CheckoutState.OPEN

    def _ensure_open(self) -> None:
        if self.checkout_state is not CheckoutState.OPEN:
            raise RuntimeError("A sessão está em processo de finalização.")

    def _invalidate_payment(self) -> None:
        self.payment_plan = None
        self.credit_terms = None

    @property
    def items_total(self) -> Decimal:
        return self.cart.total

    @property
    def total(self) -> Decimal:
        return (self.items_total - self.discount_amount + self.surcharge_amount).quantize(
            MoneyCodec.CENT
        )

    def select_customer(self, customer_id: int) -> None:
        self._ensure_open()
        if isinstance(customer_id, bool) or int(customer_id) <= 0:
            raise ValueError("Cliente inválido.")
        self.customer_id = int(customer_id)

    def clear_customer(self) -> None:
        self._ensure_open()
        self.customer_id = None

    def add_item(self, item: CartItem) -> CartItem:
        self._ensure_open()
        added = self.cart.add(item)
        self._invalidate_payment()
        return added

    def remove_item(self, line_id: str) -> CartItem:
        self._ensure_open()
        removed = self.cart.remove(line_id)
        self._invalidate_payment()
        return removed

    def change_quantity(self, line_id: str, quantity: Decimal | int | str) -> CartItem:
        self._ensure_open()
        updated = self.cart.change_quantity(line_id, quantity)
        self._invalidate_payment()
        return updated

    def change_unit_price(
        self,
        line_id: str,
        unit_price: Decimal | int | str,
        *,
        allowed: bool,
    ) -> CartItem:
        self._ensure_open()
        updated = self.cart.change_unit_price(line_id, unit_price, allowed=allowed)
        self._invalidate_payment()
        return updated

    def set_adjustments(
        self,
        *,
        discount_amount: Decimal | int | str = Decimal("0.00"),
        surcharge_amount: Decimal | int | str = Decimal("0.00"),
    ) -> None:
        self._ensure_open()
        try:
            discount = MoneyCodec.parse(discount_amount, field="desconto")
            surcharge = MoneyCodec.parse(surcharge_amount, field="acréscimo")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        if discount < 0 or surcharge < 0:
            raise ValueError("Desconto e acréscimo não podem ser negativos.")
        if discount > self.items_total:
            raise ValueError("O desconto não pode ultrapassar o total dos itens.")
        if self.items_total - discount + surcharge <= 0:
            raise ValueError("O total final deve ser maior que zero.")
        self.discount_amount = discount
        self.surcharge_amount = surcharge
        self._invalidate_payment()

    def set_payment_plan(
        self,
        payment_plan: PaymentPlan,
        *,
        credit_terms: CreditTerms | None = None,
    ) -> None:
        self._ensure_open()
        if not isinstance(payment_plan, PaymentPlan):
            raise TypeError("Plano de pagamentos inválido.")
        payment_plan.validate_against(self.total)
        if payment_plan.has_store_credit:
            if credit_terms is None:
                raise ValueError("Crediário exige condições de crédito.")
            if credit_terms.financed_value != payment_plan.financed_value:
                raise ValueError("As parcelas não correspondem ao valor financiado.")
            if credit_terms.down_payment != payment_plan.entrance_value(self.total):
                raise ValueError("A entrada do crediário não corresponde aos pagamentos.")
        elif credit_terms is not None:
            raise ValueError("Condições de crédito foram informadas sem crediário.")
        self.payment_plan = payment_plan
        self.credit_terms = credit_terms

    def build_checkout_command(self) -> CheckoutCommand:
        self._ensure_open()
        if self.customer_id is None:
            raise ValueError("Selecione um cliente para finalizar a venda.")
        if self.cart.is_empty:
            raise ValueError("O carrinho de compras está vazio.")
        if self.payment_plan is None:
            raise ValueError("Prepare os pagamentos antes de finalizar a venda.")
        return CheckoutCommand(
            customer_id=self.customer_id,
            items=self.cart.items,
            payment_plan=self.payment_plan,
            credit_terms=self.credit_terms,
            discount_amount=self.discount_amount,
            surcharge_amount=self.surcharge_amount,
        )

    def begin_checkout(self) -> None:
        self._ensure_open()
        self.checkout_state = CheckoutState.CHECKING_OUT

    def checkout_failed(self) -> None:
        self.checkout_state = CheckoutState.OPEN

    def consume_after_commit(self) -> None:
        if self.checkout_state is not CheckoutState.CHECKING_OUT:
            raise RuntimeError("A sessão não possui checkout confirmado para consumir.")
        self.reset()

    def reset(self) -> None:
        self.cart.clear()
        self.customer_id = None
        self.payment_plan = None
        self.credit_terms = None
        self.discount_amount = MoneyCodec.ZERO
        self.surcharge_amount = MoneyCodec.ZERO
        self.checkout_state = CheckoutState.OPEN
