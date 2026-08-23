from __future__ import annotations

from decimal import Decimal

from commercial.application.dto import SuspendedSale
from commercial.domain.cart import CartItem
from services.pdv_service import PDVService


class NabiCodeSuspendedSaleGateway:
    """Adapta a porta Commercial ao armazenamento oficial de vendas suspensas."""

    def __init__(self, pdv: PDVService) -> None:
        self._pdv = pdv

    @staticmethod
    def _stored_item(item: CartItem) -> dict:
        return {
            "produto_id": item.product_id,
            "item": item.description,
            "qtd": item.quantity,
            "preco_original": item.unit_price,
            "desconto_percentual": item.discount_percent,
            "preco": item.net_unit_price,
            "subtotal": item.subtotal,
            "item_avulso": item.is_loose,
        }

    @staticmethod
    def _cart_item(item: dict) -> CartItem:
        product_id = item.get("produto_id")
        return CartItem(
            description=str(item.get("item") or ""),
            quantity=Decimal(str(item.get("qtd", "0"))),
            unit_price=Decimal(str(item.get("preco_original", item.get("preco", "0")))),
            product_id=int(product_id) if product_id not in (None, "", 0, "0") else None,
            discount_percent=Decimal(str(item.get("desconto_percentual", "0"))),
        )

    def _document(self, stored) -> SuspendedSale:
        customer_id = stored.cliente_id
        return SuspendedSale(
            suspended_id=stored.id,
            created_at=stored.criada_em,
            customer_id=customer_id,
            customer_name=stored.cliente_nome if customer_id is not None else "",
            items=tuple(self._cart_item(item) for item in stored.itens),
            total=stored.total,
        )

    def suspend(
        self, *, customer_id: int | None, customer_name: str, items: tuple[CartItem, ...]
    ) -> SuspendedSale:
        stored = self._pdv.suspender(
            [self._stored_item(item) for item in items],
            cliente_id=customer_id,
            cliente_nome=customer_name if customer_id is not None else "",
        )
        return self._document(stored)

    def list_open(self) -> tuple[SuspendedSale, ...]:
        return tuple(self._document(item) for item in self._pdv.listar_suspensas())

    def resume(self, suspended_id: str) -> SuspendedSale:
        return self._document(self._pdv.reabrir(str(suspended_id)))
