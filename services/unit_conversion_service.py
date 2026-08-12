from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class UnitConversionService:
    """Conversão segura da unidade de compra para a unidade de estoque."""

    @staticmethod
    def validar_fator(fator: Any) -> float:
        try:
            value = Decimal(str(fator).strip().replace(",", "."))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Fator de conversão inválido.") from exc
        if value <= 0:
            raise ValueError("O fator de conversão deve ser maior que zero.")
        if value > Decimal("1000000"):
            raise ValueError("O fator de conversão informado é muito alto.")
        return float(value)

    @classmethod
    def para_estoque(cls, quantidade_compra: Any, fator: Any) -> float:
        try:
            quantity = Decimal(str(quantidade_compra).strip().replace(",", "."))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Quantidade inválida.") from exc
        if quantity < 0:
            raise ValueError("A quantidade não pode ser negativa.")
        valid_factor = Decimal(str(cls.validar_fator(fator)))
        return float(quantity * valid_factor)

    @classmethod
    def custo_unitario_estoque(cls, custo_unidade_compra: Any, fator: Any) -> float:
        try:
            cost = Decimal(str(custo_unidade_compra).strip().replace(",", "."))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Custo de compra inválido.") from exc
        if cost < 0:
            raise ValueError("O custo não pode ser negativo.")
        valid_factor = Decimal(str(cls.validar_fator(fator)))
        return float(cost / valid_factor)
