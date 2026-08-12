from __future__ import annotations

from decimal import Decimal
from typing import Any

from services.pricing_service import PricingService
from services.unit_conversion_service import UnitConversionService


class ProductValidator:
    """Validações compartilhadas pelos fluxos de cadastro de produtos."""

    @staticmethod
    def normalize_name(value: Any, *, message: str = "Informe o nome do produto.", uppercase: bool = False) -> str:
        name = " ".join(str(value or "").split())
        if not name:
            raise ValueError(message)
        return name.upper() if uppercase else name

    @staticmethod
    def normalize_type(value: Any) -> str:
        normalized = str(value or "").strip().upper().replace("Ç", "C").replace("Í", "I")
        if normalized in {"SERVICO", "MERCADORIA"}:
            return normalized
        raise ValueError("Tipo de produto inválido.")

    @classmethod
    def normalize_filter_type(cls, value: Any) -> str:
        normalized = str(value or "TODOS").strip().upper()
        return "TODOS" if normalized == "TODOS" else cls.normalize_type(normalized)

    @staticmethod
    def validate_values(
        *,
        sale_price: Decimal | float,
        cost_price: Decimal | float = Decimal("0"),
        expenses_percent: Decimal | float = Decimal("0"),
        profit_margin: Decimal | float = Decimal("0"),
        conversion_factor: Decimal | float = Decimal("1"),
        current_stock: Decimal | float = Decimal("0"),
        minimum_stock: Decimal | float = Decimal("0"),
        allow_negative_stock: bool = False,
    ) -> None:
        if Decimal(str(sale_price)) < 0:
            raise ValueError("Preço de venda não pode ser negativo.")
        PricingService.calcular(cost_price, expenses_percent, profit_margin)
        UnitConversionService.validar_fator(conversion_factor)
        if Decimal(str(minimum_stock)) < 0:
            raise ValueError("Estoque mínimo não pode ser negativo.")
        if Decimal(str(current_stock)) < 0 and not allow_negative_stock:
            raise ValueError("Estoque não pode ser negativo sem autorização.")
