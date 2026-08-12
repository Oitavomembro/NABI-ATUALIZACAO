from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from .product_application_service import ProductApplicationService, ProductPricingState


class EntryControl(Protocol):
    def get(self) -> Any: ...
    def delete(self, start: Any, end: Any) -> Any: ...
    def insert(self, index: Any, value: Any) -> Any: ...


@dataclass(frozen=True)
class ProductPricingControls:
    custo: EntryControl
    despesas_percentual: EntryControl
    margem_lucro: EntryControl
    preco_venda: EntryControl

    def __post_init__(self) -> None:
        for nome, control in self.__dict__.items():
            if not all(callable(getattr(control, metodo, None)) for metodo in ("get", "delete", "insert")):
                raise TypeError(f"Controle de preço incompatível: {nome}.")


class ProductPricingController:
    """Sincroniza custo, despesas, margem e preço sem depender de Tkinter."""

    def __init__(self, controls: ProductPricingControls, application_service: type[ProductApplicationService] = ProductApplicationService) -> None:
        self.controls = controls
        self.application_service = application_service
        self._updating = False

    @property
    def updating(self) -> bool:
        return self._updating

    @staticmethod
    def _read(control: EntryControl) -> str:
        return str(control.get()).strip()

    @staticmethod
    def _format(value: Any) -> str:
        try:
            decimal_value = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Valor numérico inválido: {value}") from exc
        return format(decimal_value.quantize(Decimal("0.01")), "f").replace(".", ",")

    @classmethod
    def _write(cls, control: EntryControl, value: Any) -> bool:
        text = cls._format(value)
        if str(control.get()).strip() == text:
            return False
        control.delete(0, "end")
        control.insert(0, text)
        return True

    def _apply(self, control: EntryControl, value: str) -> bool:
        if self._updating:
            return False
        self._updating = True
        try:
            return self._write(control, value)
        finally:
            self._updating = False

    def calculate_sale_price(self, *, ignore_invalid: bool = True) -> ProductPricingState | None:
        if self._updating:
            return None
        try:
            if self.application_service.converter_numero(self._read(self.controls.custo)) <= 0:
                return None
            state = self.application_service.calcular_preco_formulario(
                self._read(self.controls.custo), self._read(self.controls.despesas_percentual), self._read(self.controls.margem_lucro)
            )
        except (TypeError, ValueError):
            if ignore_invalid:
                return None
            raise
        self._apply(self.controls.preco_venda, state.preco_venda)
        return state

    def calculate_margin(self, *, ignore_invalid: bool = True) -> ProductPricingState | None:
        if self._updating:
            return None
        try:
            state = self.application_service.calcular_margem_formulario(
                self._read(self.controls.custo), self._read(self.controls.despesas_percentual), self._read(self.controls.preco_venda)
            )
        except (TypeError, ValueError):
            if ignore_invalid:
                return None
            raise
        self._apply(self.controls.margem_lucro, state.margem_lucro)
        return state

    def on_cost_or_margin_changed(self, _event: Any = None) -> ProductPricingState | None:
        return self.calculate_sale_price(ignore_invalid=True)

    def on_sale_price_changed(self, _event: Any = None) -> ProductPricingState | None:
        return self.calculate_margin(ignore_invalid=True)

    def apply_suggested_price(self) -> ProductPricingState:
        state = self.calculate_sale_price(ignore_invalid=False)
        if state is None:
            raise ValueError("Informe um preço de custo maior que zero.")
        return state
