from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import unicodedata
from typing import Any

from repositories import NFeImportRepository
from .nfe_xml_service import NFeDocument, NFeItem


@dataclass(frozen=True)
class NFeProductCandidate:
    produto_id: int
    codigo: str
    nome: str
    codigo_barras: str
    similaridade: float
    criterio: str


@dataclass(frozen=True)
class NFeItemAnalysis:
    index: int
    item: NFeItem
    produto_id: int | None
    status: str
    criterio: str
    similaridade: float = 0.0
    candidatos: tuple[NFeProductCandidate, ...] = ()


class NFeMatchingService:
    def __init__(self, repository: NFeImportRepository) -> None:
        self.repository = repository

    @staticmethod
    def normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(text or "").casefold())
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return " ".join("".join(ch if ch.isalnum() else " " for ch in normalized).split())

    @classmethod
    def candidate(cls, item: NFeItem, product: dict[str, Any]) -> NFeProductCandidate:
        xml_ean = str(item.codigo_barras or "").strip().casefold()
        product_ean = str(product.get("codigo_barras") or "").strip().casefold()
        xml_code = cls.normalize(item.codigo)
        product_code = cls.normalize(product.get("codigo") or "")
        xml_name = cls.normalize(item.descricao)
        product_name = cls.normalize(product.get("nome") or "")
        if xml_ean and xml_ean not in {"sem gtin", "semgtin"} and xml_ean == product_ean:
            percentage, criterion = 100.0, "EAN"
        elif xml_code and xml_code == product_code:
            percentage, criterion = 100.0, "CÓDIGO"
        else:
            percentage = round(SequenceMatcher(None, xml_name, product_name).ratio() * 100, 2)
            criterion = "NOME"
        return NFeProductCandidate(
            produto_id=int(product["id"]),
            codigo=str(product.get("codigo") or ""),
            nome=str(product.get("nome") or ""),
            codigo_barras=str(product.get("codigo_barras") or ""),
            similaridade=percentage,
            criterio=criterion,
        )

    def analyze(self, document: NFeDocument) -> list[NFeItemAnalysis]:
        products = self.repository.listar_produtos_referencia()
        results: list[NFeItemAnalysis] = []
        for index, item in enumerate(document.itens):
            candidates = sorted(
                (self.candidate(item, product) for product in products),
                key=lambda candidate: (-candidate.similaridade, candidate.nome.casefold(), candidate.produto_id),
            )
            relevant = tuple(candidate for candidate in candidates[:5] if candidate.similaridade >= 45.0)
            exact = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.similaridade == 100.0 and candidate.criterio in {"EAN", "CÓDIGO"}
                ),
                None,
            )
            if exact is None:
                exact_product = self.repository.localizar_produto(
                    item.codigo,
                    item.codigo_barras,
                    item.descricao,
                )
                if exact_product:
                    exact = self.candidate(item, exact_product)
            if exact:
                results.append(
                    NFeItemAnalysis(
                        index,
                        item,
                        exact.produto_id,
                        "VINCULAR",
                        exact.criterio,
                        exact.similaridade,
                        relevant,
                    )
                )
            elif relevant:
                best = relevant[0]
                results.append(
                    NFeItemAnalysis(
                        index,
                        item,
                        best.produto_id,
                        "REVISAR",
                        best.criterio,
                        best.similaridade,
                        relevant,
                    )
                )
            else:
                results.append(NFeItemAnalysis(index, item, None, "NOVO", "NENHUM", 0.0, ()))
        return results
