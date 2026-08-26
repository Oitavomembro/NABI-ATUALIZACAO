from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re


@dataclass(frozen=True, slots=True)
class PackagingFactorSuggestion:
    factor: Decimal
    content: Decimal | None
    content_unit: str
    confidence: str
    evidence: str
    requires_confirmation: bool = True


class NFePackagingFactorService:
    """Sugere embalagem pela descrição; nunca confirma nem inventa vínculo."""

    _MULTIPACK = re.compile(
        r"(?<!\d)(?P<factor>\d{1,4})\s*[X×]\s*(?P<content>\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>ML|L|KG|G|UN|UND|PC|PCT)(?![A-Z])", re.IGNORECASE,
    )
    _COUNT = re.compile(
        r"(?:CX|CAIXA|PCT|PACOTE|FD|FARDO)\s*(?:C/|COM)?\s*(?P<factor>\d{1,4})\s*(?:UN|UND|PC)?\b",
        re.IGNORECASE,
    )

    @classmethod
    def suggest_from_description(cls, description: object) -> PackagingFactorSuggestion | None:
        text = " ".join(str(description or "").upper().split())
        match = cls._MULTIPACK.search(text)
        if match:
            factor = Decimal(match.group("factor")); content = Decimal(match.group("content").replace(",", "."))
            if factor > 1 and content > 0:
                return PackagingFactorSuggestion(
                    factor, content, match.group("unit").upper(), "ALTA",
                    f"Descrição do XML contém {match.group(0)}.",
                )
        match = cls._COUNT.search(text)
        if match and Decimal(match.group("factor")) > 1:
            factor = Decimal(match.group("factor"))
            return PackagingFactorSuggestion(
                factor, None, "UN", "MÉDIA",
                f"Descrição do XML indica embalagem com {factor} unidades.",
            )
        return None
