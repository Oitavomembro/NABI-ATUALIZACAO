from __future__ import annotations

from decimal import Decimal
from typing import Any

from commercial.application.dto import ProductRecord


class NabiCodeProductGateway:
    """Adapta ProdutoService e preserva seus caminhos de busca existentes."""

    def __init__(self, product_service) -> None:
        self.product_service = product_service

    @staticmethod
    def _record(data: dict[str, Any]) -> ProductRecord:
        return ProductRecord(
            product_id=int(data["id"]),
            code=str(data.get("codigo") or ""),
            barcode=str(data.get("codigo_barras") or ""),
            description=str(data.get("nome") or data.get("descricao") or ""),
            unit_price=Decimal(str(data.get("preco_venda") or 0)),
            active=bool(data.get("ativo", True)),
            current_stock=Decimal(str(data.get("estoque_atual") or 0)),
            unit_code=str(data.get("unidade") or "UN"),
            barcodes=tuple(data.get("codigos_barras") or ()),
            # Bancos legados não possuíam esta política e historicamente
            # aceitavam quantidades decimais. A migração define o padrão novo.
            allows_fractional_quantity=bool(data.get("permite_fracionado", True)),
        )

    def search(self, term: str, *, limit: int = 30) -> tuple[ProductRecord, ...]:
        safe_limit = max(1, min(int(limit), 200))
        try:
            rows = self.product_service.listar(str(term or ""), limit=safe_limit)
        except TypeError as exc:
            if "unexpected keyword argument 'limit'" not in str(exc):
                raise
            # Compatibilidade com portas de terceiros anteriores ao limite SQL.
            rows = self.product_service.listar(str(term or ""))[:safe_limit]
        return tuple(
            self._record(data)
            for data in rows
        )

    def get(self, product_id: int) -> ProductRecord | None:
        normalized_id = int(product_id)
        if normalized_id <= 0:
            return None
        data = self.product_service.buscar(normalized_id)
        return self._record(data) if data is not None else None
