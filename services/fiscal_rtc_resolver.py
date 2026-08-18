from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


@dataclass(frozen=True)
class FiscalRtcRule:
    cst: str
    classification: str
    ibs_uf_rate: str
    ibs_city_rate: str
    cbs_rate: str
    taxable: bool


class FiscalRtcResolver:
    """Matriz RTC deliberadamente limitada aos cenários comerciais homologáveis."""

    REGULAR_CLASSIFICATION = "000001"
    EXPORT_CLASSIFICATION = "410004"

    @classmethod
    def resolve(cls, values: Mapping[str, Any], *, destination: int) -> FiscalRtcRule:
        if destination == 3:
            return FiscalRtcRule("410", cls.EXPORT_CLASSIFICATION, "0", "0", "0", False)
        if destination not in {1, 2}:
            raise ValueError("Destino fiscal inválido para IBS/CBS.")
        cst = cls._digits(values.get("ibs_cbs_cst"))
        classification = cls._digits(values.get("ibs_cbs_class"))
        if (cst, classification) != ("000", cls.REGULAR_CLASSIFICATION):
            raise ValueError(
                "Esta etapa aceita venda nacional regular com CST 000 e classificação 000001. "
                "Regimes especiais exigem regra fiscal própria aprovada."
            )
        rates = tuple(
            cls._rate(values.get(field), label)
            for field, label in (
                ("ibs_uf_rate", "IBS estadual"),
                ("ibs_city_rate", "IBS municipal"),
                ("cbs_rate", "CBS"),
            )
        )
        return FiscalRtcRule(cst, classification, *rates, True)

    @staticmethod
    def _digits(value: Any) -> str:
        return "".join(character for character in str("" if value is None else value) if character.isdigit())

    @staticmethod
    def _rate(value: Any, label: str) -> str:
        try:
            rate = Decimal(str(value or "0").replace(",", "."))
        except InvalidOperation as exc:
            raise ValueError(f"Alíquota {label} inválida.") from exc
        if rate < 0 or rate > 100:
            raise ValueError(f"Alíquota {label} deve ficar entre 0 e 100%.")
        return format(rate.normalize(), "f")
