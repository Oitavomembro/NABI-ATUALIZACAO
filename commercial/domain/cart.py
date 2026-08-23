from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable
from uuid import uuid4

from .money import MoneyCodec, MoneyValueError


def _quantity(value: Decimal | int | str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("A quantidade deve ser informada sem ponto flutuante binário.")
    try:
        quantity = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Quantidade inválida.") from exc
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")
    return quantity


def _discount(value: Decimal | int | str) -> Decimal:
    try:
        discount = MoneyCodec.parse(value, field="desconto percentual")
    except MoneyValueError as exc:
        raise ValueError(str(exc)) from exc
    if discount < 0 or discount > 100:
        raise ValueError("O desconto deve estar entre 0 e 100%.")
    return discount


@dataclass(frozen=True, slots=True)
class CartItem:
    description: str
    quantity: Decimal
    unit_price: Decimal
    product_id: int | None = None
    discount_percent: Decimal = Decimal("0.00")
    line_id: str = ""

    def __post_init__(self) -> None:
        description = str(self.description or "").strip()
        if not description:
            raise ValueError("A descrição do item é obrigatória.")
        product_id = self.product_id
        if product_id is not None:
            if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
                raise ValueError("product_id deve ser positivo quando informado.")
        try:
            unit_price = MoneyCodec.parse(self.unit_price, field="preço unitário")
        except MoneyValueError as exc:
            raise ValueError(str(exc)) from exc
        if unit_price < 0:
            raise ValueError("O preço unitário não pode ser negativo.")

        object.__setattr__(self, "description", description)
        object.__setattr__(self, "quantity", _quantity(self.quantity))
        object.__setattr__(self, "unit_price", unit_price)
        object.__setattr__(self, "product_id", product_id)
        object.__setattr__(self, "discount_percent", _discount(self.discount_percent))
        line_id = str(self.line_id or "").strip() or uuid4().hex
        object.__setattr__(self, "line_id", line_id)

    @property
    def is_loose(self) -> bool:
        return self.product_id is None

    @property
    def net_unit_price(self) -> Decimal:
        multiplier = Decimal("1") - self.discount_percent / Decimal("100")
        return (self.unit_price * multiplier).quantize(
            MoneyCodec.CENT, rounding=ROUND_HALF_UP
        )

    @property
    def subtotal(self) -> Decimal:
        return (self.quantity * self.net_unit_price).quantize(
            MoneyCodec.CENT, rounding=ROUND_HALF_UP
        )


class Cart:
    """Agregado mutável com linhas imutáveis e exposição somente por tupla."""

    def __init__(self, items: Iterable[CartItem] = ()) -> None:
        self._items: list[CartItem] = []
        for item in items:
            self.add(item)

    @property
    def items(self) -> tuple[CartItem, ...]:
        return tuple(self._items)

    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self._items), MoneyCodec.ZERO).quantize(
            MoneyCodec.CENT, rounding=ROUND_HALF_UP
        )

    @property
    def is_empty(self) -> bool:
        return not self._items

    def add(self, item: CartItem) -> CartItem:
        if not isinstance(item, CartItem):
            raise TypeError("O carrinho aceita somente CartItem.")
        if any(existing.line_id == item.line_id for existing in self._items):
            raise ValueError("Já existe um item com este line_id no carrinho.")
        self._items.append(item)
        return item

    def _index(self, line_id: str) -> int:
        normalized = str(line_id or "")
        for index, item in enumerate(self._items):
            if item.line_id == normalized:
                return index
        raise KeyError("Item não encontrado no carrinho.")

    def remove(self, line_id: str) -> CartItem:
        return self._items.pop(self._index(line_id))

    def change_quantity(self, line_id: str, quantity: Decimal | int | str) -> CartItem:
        index = self._index(line_id)
        updated = replace(self._items[index], quantity=_quantity(quantity))
        self._items[index] = updated
        return updated

    def change_unit_price(
        self,
        line_id: str,
        unit_price: Decimal | int | str,
        *,
        allowed: bool = False,
    ) -> CartItem:
        if not allowed:
            raise PermissionError("A alteração do preço não foi autorizada.")
        index = self._index(line_id)
        updated = replace(self._items[index], unit_price=unit_price)
        self._items[index] = updated
        return updated

    def clear(self) -> None:
        self._items.clear()
