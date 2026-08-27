from __future__ import annotations

from dataclasses import dataclass

from licensing.models import LicenseEdition


@dataclass(frozen=True, slots=True)
class LicensedProduct:
    product_id: str
    label: str
    editions: tuple[LicenseEdition, ...]
    default_edition: LicenseEdition
    features: dict[LicenseEdition, tuple[str, ...]]
    key_id_prefix: str | None = None


PRODUCTS = (
    LicensedProduct(
        "NABICODE", "NabiCode",
        (LicenseEdition.COMMERCIAL, LicenseEdition.FICHARIO, LicenseEdition.EVALUATION),
        LicenseEdition.FICHARIO,
        {
            LicenseEdition.COMMERCIAL: ("assistant", "commercial", "legacy", "qt"),
            LicenseEdition.FICHARIO: ("commercial", "fichario", "financial", "qt"),
            LicenseEdition.EVALUATION: ("assistant", "commercial", "qt"),
        },
        None,
    ),
    LicensedProduct(
        "NOTAS_IGLBALT", "Notas IglBalt", (LicenseEdition.COMPLETE,),
        LicenseEdition.COMPLETE, {LicenseEdition.COMPLETE: ("core",)},
        "notas-iglbalt-",
    ),
)
PRODUCTS_BY_ID = {item.product_id: item for item in PRODUCTS}


def product(product_id: str) -> LicensedProduct:
    try:
        return PRODUCTS_BY_ID[str(product_id).strip().upper()]
    except KeyError as exc:
        raise ValueError("Produto de licença desconhecido.") from exc
