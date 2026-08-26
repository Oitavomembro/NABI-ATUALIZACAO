_NO_GTIN = frozenset({"SEM GTIN", "SEMGTIN", "NO GTIN", "NOGTIN"})


def normalize_gtin(value: object) -> str:
    """Normaliza sentinelas do XML sem transformar ausência em identidade."""
    text = " ".join(str(value or "").strip().upper().split())
    return "" if text in _NO_GTIN else str(value or "").strip()

