from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from .purchase_drafts import _CENT, _QTY, _decimal_text


def _text(value, *, field: str, maximum: int, required: bool = False) -> str:
    result = " ".join(str(value or "").split())
    if required and not result:
        raise ValueError(f"{field} é obrigatório.")
    if len(result) > maximum:
        raise ValueError(f"{field} excede o tamanho permitido.")
    return result


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


class _Catalog:
    def __init__(self, maximum: int = 20) -> None:
        self._maximum = max(1, min(int(maximum), 100))
        self._drafts = OrderedDict()
        self._lock = Lock()

    def _store(self, draft):
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > self._maximum:
                self._drafts.popitem(last=False)
        return draft

    def get(self, draft_id: str):
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Rascunho de compra não encontrado ou descartado.")
        return draft


@dataclass(frozen=True, slots=True)
class SupplierRegistrationDraft:
    draft_id: str
    fingerprint: str
    name: str
    legal_name: str
    document: str
    phone: str
    email: str
    operation_kind: str = "SUPPLIER_CREATE"


class SupplierRegistrationDraftService(_Catalog):
    def create(self, *, name, legal_name="", document="", phone="", email=""):
        payload = {
            "name": _text(name, field="Nome", maximum=160, required=True),
            "legal_name": _text(legal_name, field="Razão social", maximum=200),
            "document": _text(document, field="Documento", maximum=20),
            "phone": _text(phone, field="Telefone", maximum=30),
            "email": _text(email, field="E-mail", maximum=160),
        }
        return self._store(SupplierRegistrationDraft(
            uuid4().hex, _fingerprint(payload), **payload
        ))


@dataclass(frozen=True, slots=True)
class PurchaseOrderItemRequest:
    product_id: int
    quantity: Decimal
    unit_cost: Decimal

    def __post_init__(self):
        if isinstance(self.product_id, bool) or int(self.product_id) <= 0:
            raise ValueError("Produto inválido no pedido.")
        object.__setattr__(self, "product_id", int(self.product_id))
        object.__setattr__(self, "quantity", _decimal_text(
            self.quantity, field="Quantidade", quantum=_QTY
        ))
        object.__setattr__(self, "unit_cost", _decimal_text(
            self.unit_cost, field="Custo unitário", quantum=_CENT, positive=False
        ))


@dataclass(frozen=True, slots=True)
class PurchaseOrderDraftItem:
    product_id: int
    code: str
    description: str
    quantity: Decimal
    unit_cost: Decimal
    line_total: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseOrderDraft:
    draft_id: str
    fingerprint: str
    supplier_id: int
    supplier_name: str
    notes: str
    items: tuple[PurchaseOrderDraftItem, ...]
    total: Decimal
    operation_kind: str = "PURCHASE_ORDER_CREATE"


class PurchaseOrderDraftService(_Catalog):
    def __init__(self, purchase_management_service, *, maximum: int = 20, max_items: int = 50):
        if purchase_management_service is None:
            raise ValueError("O serviço oficial de compras é obrigatório.")
        super().__init__(maximum)
        self._purchases = purchase_management_service
        self._max_items = max(1, min(int(max_items), 100))

    def create(self, supplier_id: int, requests, *, notes: str = ""):
        if isinstance(supplier_id, bool) or int(supplier_id) <= 0:
            raise ValueError("Fornecedor inválido.")
        suppliers = {item.supplier_id: item for item in self._purchases.list_suppliers() if item.active}
        supplier = suppliers.get(int(supplier_id))
        if supplier is None:
            raise ValueError("Fornecedor não encontrado ou inativo.")
        normalized = tuple(
            item if isinstance(item, PurchaseOrderItemRequest)
            else PurchaseOrderItemRequest(**item) for item in requests
        )
        if not normalized or len(normalized) > self._max_items:
            raise ValueError("Informe uma quantidade segura de itens no pedido.")
        ids = [item.product_id for item in normalized]
        if len(ids) != len(set(ids)):
            raise ValueError("O mesmo produto foi informado mais de uma vez.")
        products = {item.product_id: item for item in self._purchases.list_products(int(supplier_id))}
        items = []
        for request in normalized:
            product = products.get(request.product_id)
            if product is None:
                raise ValueError("Produto não encontrado, inativo ou incompatível com o fornecedor.")
            items.append(PurchaseOrderDraftItem(
                request.product_id, product.code, product.description,
                request.quantity, request.unit_cost,
                (request.quantity * request.unit_cost).quantize(_CENT),
            ))
        frozen_items = tuple(items)
        total = sum((item.line_total for item in frozen_items), Decimal("0.00")).quantize(_CENT)
        payload = {
            "supplier_id": int(supplier_id),
            "items": [{
                "product_id": item.product_id,
                "quantity": format(item.quantity, "f"),
                "unit_cost": format(item.unit_cost, "f"),
            } for item in frozen_items],
            "notes": _text(notes, field="Observação", maximum=500),
            "total": format(total, "f"),
        }
        return self._store(PurchaseOrderDraft(
            uuid4().hex, _fingerprint(payload), int(supplier_id),
            supplier.name, payload["notes"], frozen_items, total,
        ))
