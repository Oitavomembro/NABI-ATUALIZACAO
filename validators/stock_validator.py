from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


class StockValidator:
    QUANTIZER = Decimal("0.0001")

    @classmethod
    def quantity(cls, value: Any, *, allow_zero: bool = False) -> Decimal:
        try:
            quantity = Decimal(str(value)).quantize(cls.QUANTIZER, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Quantidade de estoque inválida.") from exc
        if quantity < 0 or (quantity == 0 and not allow_zero):
            raise ValueError("A quantidade deve ser maior que zero.")
        return quantity

    @staticmethod
    def required_reason(value: Any, *, operation: str) -> str:
        reason = str(value or "").strip()
        if not reason:
            raise ValueError(f"Informe o motivo {operation}.")
        return reason
