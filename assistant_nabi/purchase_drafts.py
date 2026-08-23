from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from threading import Lock
from uuid import uuid4


_QTY = Decimal("0.0001")
_CENT = Decimal("0.01")


def _decimal_text(value, *, field: str, quantum: Decimal, positive: bool = True) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{field} deve ser informado como texto decimal.")
    try:
        result = Decimal(str(value).replace(",", ".")).quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field} inválido.") from error
    if not result.is_finite() or (positive and result <= 0) or (not positive and result < 0):
        raise ValueError(f"{field} inválido.")
    return result


@dataclass(frozen=True, slots=True)
class PurchaseReceiptItemRequest:
    order_item_id: int
    quantity: Decimal
    unit_cost: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.order_item_id, bool) or int(self.order_item_id) <= 0:
            raise ValueError("Item de pedido inválido.")
        object.__setattr__(self, "order_item_id", int(self.order_item_id))
        object.__setattr__(self, "quantity", _decimal_text(
            self.quantity, field="Quantidade recebida", quantum=_QTY
        ))
        object.__setattr__(self, "unit_cost", _decimal_text(
            self.unit_cost, field="Custo unitário", quantum=_CENT, positive=False
        ))


@dataclass(frozen=True, slots=True)
class PurchaseReceiptDraftItem:
    order_item_id: int
    product_id: int
    code: str
    description: str
    quantity: Decimal
    pending_before: Decimal
    pending_after: Decimal
    unit_cost: Decimal
    line_total: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseReceiptDraft:
    draft_id: str
    fingerprint: str
    order_id: int
    supplier_id: int
    supplier_name: str
    document: str
    generate_payable: bool
    due_date: str | None
    items: tuple[PurchaseReceiptDraftItem, ...]
    total: Decimal
    operation_kind: str = "PURCHASE_RECEIPT"


class PurchaseReceiptDraftService:
    """Prepara recebimento sem alterar pedido, estoque, custo ou financeiro."""

    def __init__(self, gateway, *, max_items: int = 100) -> None:
        if gateway is None:
            raise ValueError("A porta oficial de compras é obrigatória.")
        self._gateway = gateway
        self._max_items = max(1, min(int(max_items), 200))
        self._drafts: OrderedDict[str, PurchaseReceiptDraft] = OrderedDict()
        self._lock = Lock()

    def create(
        self, order_id: int, requests, *, document: str = "",
        generate_payable: bool = False, due_date: str | None = None,
    ) -> PurchaseReceiptDraft:
        if isinstance(order_id, bool) or int(order_id) <= 0:
            raise ValueError("Pedido de compra inválido.")
        normalized = tuple(
            item if isinstance(item, PurchaseReceiptItemRequest)
            else PurchaseReceiptItemRequest(**item)
            for item in requests
        )
        if not normalized or len(normalized) > self._max_items:
            raise ValueError("Informe uma quantidade segura de itens para o recebimento.")
        ids = [item.order_item_id for item in normalized]
        if len(ids) != len(set(ids)):
            raise ValueError("O mesmo item do pedido foi informado mais de uma vez.")
        if generate_payable and not str(due_date or "").strip():
            raise ValueError("Conta a pagar exige data de vencimento.")
        order = self._gateway.get_open_order(int(order_id))
        if order is None:
            raise ValueError("Pedido de compra aberto não encontrado.")
        order_items = {int(item["id"]): item for item in order["itens"]}
        items = tuple(self._resolve(order_items, request) for request in normalized)
        total = sum((item.line_total for item in items), Decimal("0.00")).quantize(_CENT)
        payload = {
            "order_id": int(order_id), "supplier_id": int(order["fornecedor_id"]),
            "document": str(document or "").strip(),
            "generate_payable": bool(generate_payable),
            "due_date": str(due_date or "").strip() or None,
            "items": [
                {
                    "order_item_id": item.order_item_id,
                    "product_id": item.product_id,
                    "quantity": format(item.quantity, "f"),
                    "pending_before": format(item.pending_before, "f"),
                    "unit_cost": format(item.unit_cost, "f"),
                }
                for item in items
            ],
            "total": format(total, "f"),
        }
        fingerprint = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        draft = PurchaseReceiptDraft(
            uuid4().hex, fingerprint, int(order_id), int(order["fornecedor_id"]),
            str(order.get("fornecedor_nome") or ""), payload["document"],
            bool(generate_payable), payload["due_date"], items, total,
        )
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > 20:
                self._drafts.popitem(last=False)
        return draft

    def get(self, draft_id: str) -> PurchaseReceiptDraft:
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Rascunho de recebimento não encontrado ou descartado.")
        return draft

    @staticmethod
    def _resolve(order_items, request: PurchaseReceiptItemRequest) -> PurchaseReceiptDraftItem:
        item = order_items.get(request.order_item_id)
        if item is None:
            raise ValueError("Item não pertence ao pedido informado.")
        pending = _decimal_text(
            item.get("quantidade_pendente"), field="Saldo pendente", quantum=_QTY
        )
        if request.quantity > pending:
            raise ValueError(f"Quantidade recebida de {item.get('codigo') or ''} excede o saldo pendente.")
        return PurchaseReceiptDraftItem(
            request.order_item_id, int(item["produto_id"]), str(item.get("codigo") or ""),
            str(item.get("nome") or ""), request.quantity, pending,
            (pending - request.quantity).quantize(_QTY), request.unit_cost,
            (request.quantity * request.unit_cost).quantize(_CENT, rounding=ROUND_HALF_UP),
        )
