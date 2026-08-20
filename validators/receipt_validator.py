from __future__ import annotations

from typing import Any, Mapping, Sequence


class ReceiptValidator:
    TYPE_ALIASES = {
        "COMPROVANTE": "VENDA",
        "CUPOM": "VENDA",
        "RECIBO": "VENDA",
        "COMPRA": "VENDA",
        "NAO_FISCAL": "VENDA",
        "NÃO FISCAL": "VENDA",
        "ORCAMENTO": "ORCAMENTO",
        "ORÇAMENTO": "ORCAMENTO",
    }

    @classmethod
    def sale_header(
        cls,
        document_type: str,
        items: Sequence[Mapping[str, Any]],
        total: Any,
    ) -> tuple[str, float]:
        kind = str(document_type or "").strip().upper()
        kind = cls.TYPE_ALIASES.get(kind, kind)
        if kind not in {"VENDA", "ENTREGA", "ORCAMENTO"}:
            raise ValueError("Tipo de comprovante inválido.")
        if not items:
            raise ValueError("O comprovante precisa possuir ao menos um item.")
        try:
            normalized_total = float(total)
        except (TypeError, ValueError) as exc:
            raise ValueError("Total inválido para emissão do comprovante.") from exc
        if normalized_total < 0:
            raise ValueError("O total do comprovante não pode ser negativo.")
        return kind, normalized_total

    @staticmethod
    def sale_item(item: Mapping[str, Any]) -> tuple[str, float, float, float]:
        name = str(item.get("item") or "").strip()
        if not name:
            raise ValueError("Item sem descrição no comprovante.")
        try:
            quantity = float(item["qtd"])
            price = float(item["preco"])
            subtotal = float(item["subtotal"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Valores inválidos no item {name}.") from exc
        if quantity <= 0 or price < 0 or subtotal < 0:
            raise ValueError(f"Valores inválidos no item {name}.")
        return name, quantity, price, subtotal

    @staticmethod
    def matching_total(calculated_total: float, declared_total: float) -> None:
        if abs(calculated_total - declared_total) > 0.02:
            raise ValueError("O total do comprovante não corresponde à soma dos itens.")
