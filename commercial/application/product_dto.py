from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from commercial.domain.money import MoneyCodec
from .action_dto import ActionContext, ActionSensitivity


QUANTITY = Decimal("0.0001")


def quantity(value, *, field_name: str = "quantidade", allow_zero: bool = True,
             allow_negative: bool = False) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{field_name} deve ser informado sem ponto flutuante binário.")
    try:
        result = Decimal(str(value)).quantize(QUANTITY)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} inválida.") from exc
    if (result < 0 and not allow_negative) or (not allow_zero and result == 0):
        raise ValueError(f"{field_name} deve ser positiva.")
    return result


@dataclass(frozen=True, slots=True)
class ProductCreateCommand:
    code: str
    description: str
    sale_price: Decimal
    product_type: str = "MERCADORIA"
    barcode: str = ""
    cost_price: Decimal = Decimal("0.00")
    current_stock: Decimal = Decimal("0.0000")
    minimum_stock: Decimal = Decimal("0.0000")
    allow_negative_stock: bool = False
    category_id: int | None = None
    ncm: str = ""
    cest: str = ""
    unit_code: str = ""

    def __post_init__(self) -> None:
        if not str(self.description or "").strip():
            raise ValueError("Descrição do produto obrigatória.")
        object.__setattr__(self, "sale_price", MoneyCodec.parse(self.sale_price, field="preço de venda"))
        object.__setattr__(self, "cost_price", MoneyCodec.parse(self.cost_price, field="preço de custo"))
        object.__setattr__(self, "current_stock", quantity(self.current_stock, field_name="estoque atual", allow_negative=self.allow_negative_stock))
        object.__setattr__(self, "minimum_stock", quantity(self.minimum_stock, field_name="estoque mínimo"))


@dataclass(frozen=True, slots=True)
class ProductUpdateCommand(ProductCreateCommand):
    product_id: int = 0

    def __post_init__(self) -> None:
        ProductCreateCommand.__post_init__(self)
        if int(self.product_id) <= 0:
            raise ValueError("Produto inválido.")
        object.__setattr__(self, "product_id", int(self.product_id))


@dataclass(frozen=True, slots=True)
class ProductDetails:
    product_id: int
    code: str
    barcode: str
    description: str
    sale_price: Decimal
    cost_price: Decimal
    current_stock: Decimal
    minimum_stock: Decimal
    allow_negative_stock: bool
    product_type: str
    active: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "sale_price", MoneyCodec.parse(self.sale_price, field="preço de venda"))
        object.__setattr__(self, "cost_price", MoneyCodec.parse(self.cost_price, field="preço de custo"))
        object.__setattr__(self, "current_stock", quantity(self.current_stock, field_name="estoque atual", allow_negative=True))
        object.__setattr__(self, "minimum_stock", quantity(self.minimum_stock, field_name="estoque mínimo"))


@dataclass(frozen=True, slots=True)
class ProductStockSummary:
    product_id: int
    current_quantity: Decimal
    minimum_quantity: Decimal
    available: bool
    status: str
    allow_negative_stock: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "current_quantity", quantity(self.current_quantity, field_name="estoque atual", allow_negative=True))
        object.__setattr__(self, "minimum_quantity", quantity(self.minimum_quantity, field_name="estoque mínimo"))


@dataclass(frozen=True, slots=True)
class StockMovementSummary:
    movement_id: int
    product_id: int
    occurred_at: datetime
    movement_type: str
    quantity: Decimal
    previous_balance: Decimal
    resulting_balance: Decimal
    origin: str
    reference: str
    notes: str
    user: str

    def __post_init__(self) -> None:
        for name in ("quantity", "previous_balance", "resulting_balance"):
            object.__setattr__(self, name, quantity(
                getattr(self, name), field_name=name, allow_negative=True
            ))


@dataclass(frozen=True, slots=True)
class LowStockProductSummary:
    product_id: int
    code: str
    description: str
    current_quantity: Decimal
    minimum_quantity: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "current_quantity", quantity(self.current_quantity, field_name="estoque atual", allow_negative=True))
        object.__setattr__(self, "minimum_quantity", quantity(self.minimum_quantity, field_name="estoque mínimo"))


@dataclass(frozen=True, slots=True)
class StockMovementCommand:
    product_id: int
    amount: Decimal
    reason: str
    reference: str = ""

    def __post_init__(self) -> None:
        if int(self.product_id) <= 0 or not str(self.reason or "").strip():
            raise ValueError("Produto e motivo são obrigatórios.")
        object.__setattr__(self, "product_id", int(self.product_id))
        object.__setattr__(self, "amount", quantity(self.amount, allow_zero=False))


@dataclass(frozen=True, slots=True)
class StockAdjustmentCommand:
    product_id: int
    new_balance: Decimal
    reason: str

    def __post_init__(self) -> None:
        if int(self.product_id) <= 0 or not str(self.reason or "").strip():
            raise ValueError("Produto e motivo são obrigatórios.")
        object.__setattr__(self, "product_id", int(self.product_id))
        # Saldo negativo é validado pelo backend conforme a política do produto.
        try:
            value = Decimal(str(self.new_balance)).quantize(QUANTITY)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Novo saldo inválido.") from exc
        object.__setattr__(self, "new_balance", value)


@dataclass(frozen=True, slots=True)
class PersistedStockAction:
    movement_id: int
    product_id: int
    movement_type: str
    quantity: Decimal
    previous_balance: Decimal
    resulting_balance: Decimal

    def __post_init__(self) -> None:
        for name in ("quantity", "previous_balance", "resulting_balance"):
            object.__setattr__(self, name, quantity(
                getattr(self, name), field_name=name, allow_negative=True
            ))


@dataclass(frozen=True, slots=True)
class StockActionResult:
    action: str
    context: ActionContext
    sensitivity: ActionSensitivity
    requires_human_confirmation: bool
    executed: bool
    committed: bool
    message: str
    movement_id: int | None = None
    product_id: int | None = None
    resulting_balance: Decimal | None = None
    secondary_effect_failed: bool = False


@dataclass(frozen=True, slots=True)
class StockEvent:
    kind: str
    movement_id: int
    product_id: int
    context: ActionContext
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
