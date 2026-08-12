from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any


MONEY = Decimal("0.01")


@dataclass(frozen=True)
class PricingResult:
    custo_base: Decimal
    despesas: Decimal
    custo_total: Decimal
    margem_percentual: Decimal
    lucro: Decimal
    preco_sugerido: Decimal

    def as_dict(self) -> dict[str, float]:
        return {
            "custo_base": float(self.custo_base),
            "despesas": float(self.despesas),
            "custo_total": float(self.custo_total),
            "margem_percentual": float(self.margem_percentual),
            "lucro": float(self.lucro),
            "preco_sugerido": float(self.preco_sugerido),
        }


class PricingService:
    """Motor determinístico de formação de preços.

    A margem é aplicada sobre o custo total (custo + despesas). Essa regra é
    simples, auditável e evita diferenças causadas por ponto flutuante.
    """

    @staticmethod
    def _decimal(value: Any, field: str) -> Decimal:
        try:
            normalized = str(value if value is not None else "0").strip().replace(".", "").replace(",", ".")
            # Valores numéricos vindos do Python não devem perder o ponto decimal.
            if isinstance(value, (int, float, Decimal)):
                normalized = str(value)
            result = Decimal(normalized or "0")
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{field} inválido.") from exc
        if result < 0:
            raise ValueError(f"{field} não pode ser negativo.")
        return result

    @classmethod
    def calcular(cls, custo: Any, despesas_percentual: Any = 0, margem_percentual: Any = 0) -> PricingResult:
        custo_base = cls._decimal(custo, "Custo")
        despesas_pct = cls._decimal(despesas_percentual, "Despesas")
        margem_pct = cls._decimal(margem_percentual, "Margem")
        if despesas_pct > Decimal("1000") or margem_pct > Decimal("1000"):
            raise ValueError("Percentuais acima de 1000% não são permitidos.")

        despesas = (custo_base * despesas_pct / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
        custo_total = (custo_base + despesas).quantize(MONEY, rounding=ROUND_HALF_UP)
        lucro = (custo_total * margem_pct / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
        preco = (custo_total + lucro).quantize(MONEY, rounding=ROUND_HALF_UP)
        return PricingResult(custo_base, despesas, custo_total, margem_pct, lucro, preco)
