from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FiscalOperation:
    cfop: str
    nature: str
    destination: int


class FiscalOperationResolver:
    """Resolve apenas naturezas de venda com correspondência oficial conhecida."""

    _SALE_FAMILIES = {
        "5101": ("6101", "7101", "VENDA DE PRODUCAO DO ESTABELECIMENTO"),
        "5102": ("6102", "7102", "VENDA DE MERCADORIA ADQUIRIDA DE TERCEIROS"),
        "5401": ("6401", "", "VENDA DE PRODUCAO COM SUBSTITUICAO TRIBUTARIA"),
        "5402": ("6402", "", "VENDA ENTRE CONTRIBUINTES SUBSTITUTOS"),
        "5403": ("6403", "", "VENDA DE MERCADORIA COMO SUBSTITUTO TRIBUTARIO"),
        "5405": ("6404", "", "VENDA DE MERCADORIA COM ICMS RETIDO ANTERIORMENTE"),
    }
    _BY_CFOP = {
        member: (internal, interstate, exterior, nature)
        for internal, (interstate, exterior, nature) in _SALE_FAMILIES.items()
        for member in (internal, interstate, exterior)
        if member
    }
    _MEI_CSOSN = {"102", "300", "400"}

    @classmethod
    def resolve_sale(
        cls, reference_cfop: str, *, destination: int, crt: int,
        csosn: str = "", icms_cst: str = "",
    ) -> FiscalOperation:
        reference = "".join(character for character in str(reference_cfop or "") if character.isdigit())
        if destination not in {1, 2, 3}:
            raise ValueError("Destino fiscal deve ser interno, interestadual ou exterior.")
        family = cls._BY_CFOP.get(reference)
        if family is None:
            raise ValueError(
                f"CFOP {reference or 'não informado'} não pertence a uma natureza de venda automatizada. "
                "Confirme a operação com a contabilidade."
            )
        internal, interstate, exterior, nature = family
        resolved = {1: internal, 2: interstate, 3: exterior}[destination]
        if not resolved:
            raise ValueError(
                f"A natureza {reference} não possui correspondência automática segura para este destino. "
                "Cadastre uma regra fiscal aprovada pela contabilidade."
            )
        if int(crt) == 4:
            if resolved not in {"5102", "6102"}:
                raise ValueError("MEI: esta etapa automatiza somente vendas 5102/6102.")
            normalized_csosn = "".join(character for character in str(csosn or "") if character.isdigit())
            if normalized_csosn not in cls._MEI_CSOSN:
                raise ValueError("MEI: CFOP 5102/6102 exige CSOSN 102, 300 ou 400.")
        return FiscalOperation(cfop=resolved, nature=nature, destination=destination)
