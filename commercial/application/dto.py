from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from commercial.domain.cart import CartItem
from commercial.domain.credit import CreditTerms
from commercial.domain.money import MoneyCodec, MoneyValueError
from commercial.domain.payments import Payment, PaymentPlan


@dataclass(frozen=True, slots=True)
class CustomerRecord:
    customer_id: int
    code: str
    name: str
    record_number: int | None = None
    credit_limit: Decimal | None = None
    debt_balance: Decimal | None = None

    def __post_init__(self) -> None:
        if isinstance(self.customer_id, bool) or int(self.customer_id) <= 0:
            raise ValueError("customer_id deve ser positivo.")
        name = str(self.name or "").strip()
        if not name:
            raise ValueError("O nome do cliente é obrigatório.")
        record_number = self.record_number
        if record_number is not None:
            record_number = int(record_number)
        for field_name in ("credit_limit", "debt_balance"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} deve ser Decimal quando informado.")
        object.__setattr__(self, "customer_id", int(self.customer_id))
        object.__setattr__(self, "code", str(self.code or "").strip())
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "record_number", record_number)


@dataclass(frozen=True, slots=True)
class ProductRecord:
    product_id: int
    code: str
    barcode: str
    description: str
    unit_price: Decimal
    active: bool = True
    current_stock: Decimal | None = None

    def __post_init__(self) -> None:
        if isinstance(self.product_id, bool) or int(self.product_id) <= 0:
            raise ValueError("product_id deve ser positivo.")
        description = str(self.description or "").strip()
        if not description:
            raise ValueError("A descrição do produto é obrigatória.")
        try:
            price = MoneyCodec.parse(self.unit_price, field="preço do produto")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        if price < 0:
            raise ValueError("O preço do produto não pode ser negativo.")
        object.__setattr__(self, "product_id", int(self.product_id))
        object.__setattr__(self, "code", str(self.code or "").strip())
        object.__setattr__(self, "barcode", str(self.barcode or "").strip())
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "unit_price", price)
        object.__setattr__(self, "active", bool(self.active))
        if self.current_stock is not None:
            object.__setattr__(
                self, "current_stock",
                Decimal(str(self.current_stock)).quantize(Decimal("0.0001")),
            )


@dataclass(frozen=True, slots=True)
class BudgetDocument:
    budget_id: str
    created_at: str
    customer_id: int
    customer_name: str
    items: tuple[CartItem, ...]
    total: Decimal

    def __init__(
        self,
        *,
        budget_id: str,
        created_at: str,
        customer_id: int,
        customer_name: str,
        items: Iterable[CartItem],
        total: Decimal | int | str,
    ) -> None:
        object.__setattr__(self, "budget_id", str(budget_id or "").strip())
        object.__setattr__(self, "created_at", str(created_at or "").strip())
        object.__setattr__(self, "customer_id", customer_id)
        object.__setattr__(self, "customer_name", str(customer_name or "").strip())
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "total", total)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not self.budget_id or not self.created_at:
            raise ValueError("Orçamento exige identificação e data de criação.")
        if isinstance(self.customer_id, bool) or int(self.customer_id) <= 0:
            raise ValueError("Orçamento exige customer_id real.")
        if not self.customer_name:
            raise ValueError("Orçamento exige nome do cliente.")
        if not self.items or any(not isinstance(item, CartItem) for item in self.items):
            raise ValueError("Orçamento exige itens comerciais válidos.")
        try:
            total = MoneyCodec.parse(self.total, field="total do orçamento")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        calculated = sum((item.subtotal for item in self.items), MoneyCodec.ZERO).quantize(
            MoneyCodec.CENT
        )
        if total != calculated:
            raise ValueError("O total do orçamento diverge dos itens.")
        object.__setattr__(self, "customer_id", int(self.customer_id))
        object.__setattr__(self, "total", total)


@dataclass(frozen=True, slots=True)
class SuspendedSale:
    suspended_id: str
    created_at: str
    customer_id: int | None
    customer_name: str
    items: tuple[CartItem, ...]
    total: Decimal

    def __init__(
        self, *, suspended_id: str, created_at: str,
        customer_id: int | None, customer_name: str,
        items: Iterable[CartItem], total: Decimal | int | str,
    ) -> None:
        object.__setattr__(self, "suspended_id", str(suspended_id or "").strip())
        object.__setattr__(self, "created_at", str(created_at or "").strip())
        object.__setattr__(self, "customer_id", customer_id)
        object.__setattr__(self, "customer_name", str(customer_name or "").strip())
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "total", total)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not self.suspended_id or not self.created_at:
            raise ValueError("Venda suspensa exige identificação e data de criação.")
        if self.customer_id is not None:
            if isinstance(self.customer_id, bool) or int(self.customer_id) <= 0:
                raise ValueError("customer_id da venda suspensa deve ser real.")
            object.__setattr__(self, "customer_id", int(self.customer_id))
        elif self.customer_name:
            raise ValueError("Texto sem customer_id não identifica cliente da venda suspensa.")
        if not self.items or any(not isinstance(item, CartItem) for item in self.items):
            raise ValueError("Venda suspensa exige itens comerciais válidos.")
        try:
            total = MoneyCodec.parse(self.total, field="total da venda suspensa")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        calculated = sum((item.subtotal for item in self.items), MoneyCodec.ZERO).quantize(
            MoneyCodec.CENT
        )
        if total != calculated:
            raise ValueError("O total da venda suspensa diverge dos itens.")
        object.__setattr__(self, "total", total)


@dataclass(frozen=True, slots=True)
class CheckoutCommand:
    customer_id: int
    items: tuple[CartItem, ...]
    payment_plan: PaymentPlan
    credit_terms: CreditTerms | None = None
    discount_amount: Decimal = Decimal("0.00")
    surcharge_amount: Decimal = Decimal("0.00")

    def __init__(
        self,
        *,
        customer_id: int,
        items: Iterable[CartItem],
        payment_plan: PaymentPlan,
        credit_terms: CreditTerms | None = None,
        discount_amount: Decimal | int | str = Decimal("0.00"),
        surcharge_amount: Decimal | int | str = Decimal("0.00"),
    ) -> None:
        object.__setattr__(self, "customer_id", customer_id)
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "payment_plan", payment_plan)
        object.__setattr__(self, "credit_terms", credit_terms)
        object.__setattr__(self, "discount_amount", discount_amount)
        object.__setattr__(self, "surcharge_amount", surcharge_amount)
        self.__post_init__()

    def __post_init__(self) -> None:
        if isinstance(self.customer_id, bool) or int(self.customer_id) <= 0:
            raise ValueError("customer_id deve ser positivo.")
        if not self.items or any(not isinstance(item, CartItem) for item in self.items):
            raise ValueError("CheckoutCommand exige itens comerciais válidos.")
        if not isinstance(self.payment_plan, PaymentPlan):
            raise TypeError("payment_plan inválido.")
        try:
            discount = MoneyCodec.parse(self.discount_amount, field="desconto")
            surcharge = MoneyCodec.parse(self.surcharge_amount, field="acréscimo")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        if discount < 0 or surcharge < 0:
            raise ValueError("Desconto e acréscimo não podem ser negativos.")
        object.__setattr__(self, "discount_amount", discount)
        object.__setattr__(self, "surcharge_amount", surcharge)
        if discount > self.items_total:
            raise ValueError("O desconto não pode ultrapassar o total dos itens.")
        if self.final_total <= 0:
            raise ValueError("O total final deve ser maior que zero.")
        validation = self.payment_plan.validate_against(self.final_total)
        if validation.financed_value > 0:
            if self.credit_terms is None:
                raise ValueError("Crediário exige condições de crédito.")
            if self.credit_terms.financed_value != validation.financed_value:
                raise ValueError("As parcelas não correspondem ao valor financiado.")
            if self.credit_terms.down_payment != self.payment_plan.entrance_value(self.final_total):
                raise ValueError("A entrada do crediário não corresponde aos pagamentos.")
        elif self.credit_terms is not None:
            raise ValueError("Condições de crédito foram informadas sem crediário.")
        object.__setattr__(self, "customer_id", int(self.customer_id))

    @property
    def items_total(self) -> Decimal:
        return sum((item.subtotal for item in self.items), MoneyCodec.ZERO)

    @property
    def final_total(self) -> Decimal:
        return (self.items_total - self.discount_amount + self.surcharge_amount).quantize(
            MoneyCodec.CENT
        )


@dataclass(frozen=True, slots=True)
class CheckoutReceipt:
    sale_id: int
    customer: CustomerRecord
    items: tuple[CartItem, ...]
    payments: tuple[Payment, ...]
    total: Decimal
    financed_value: Decimal
    received: Decimal
    change: Decimal
    payment_description: str
    status: str


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    success: bool
    committed: bool
    sale_id: int | None
    total: Decimal
    financed_value: Decimal
    received: Decimal
    change: Decimal
    message: str
    status: str
    session_consumed: bool
    receipt: CheckoutReceipt | None = None
    secondary_effect_failed: bool = False

    def __post_init__(self) -> None:
        try:
            total = MoneyCodec.parse(self.total, field="total")
            financed = MoneyCodec.parse(self.financed_value, field="valor financiado")
            received = MoneyCodec.parse(self.received, field="valor recebido")
            change = MoneyCodec.parse(self.change, field="troco")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        if min(total, financed, received, change) < 0 or financed > total:
            raise ValueError("CheckoutResult contém valores inválidos.")
        if self.committed:
            if not self.success or self.sale_id is None or int(self.sale_id) <= 0:
                raise ValueError("Resultado confirmado exige venda válida e sucesso.")
            if not self.session_consumed or self.receipt is None:
                raise ValueError("Venda confirmada exige sessão consumida e comprovante.")
        elif self.success or self.sale_id is not None or self.session_consumed or self.receipt is not None:
            raise ValueError("Resultado não confirmado possui estado inconsistente.")
        message = str(self.message or "").strip()
        status = str(self.status or "").strip().upper()
        if not message or not status:
            raise ValueError("Mensagem e status do checkout são obrigatórios.")
        object.__setattr__(self, "sale_id", int(self.sale_id) if self.sale_id is not None else None)
        object.__setattr__(self, "total", total)
        object.__setattr__(self, "financed_value", financed)
        object.__setattr__(self, "received", received)
        object.__setattr__(self, "change", change)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "status", status)
