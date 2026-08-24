"""Rascunhos imutáveis para cadastro comercial e estoque assistidos."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import asdict, dataclass
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from commercial.application.product_dto import (
    ProductCreateCommand, StockAdjustmentCommand, StockMovementCommand, quantity,
)


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProductCreateDraft:
    draft_id: str
    fingerprint: str
    code: str
    description: str
    sale_price: Decimal
    cost_price: Decimal
    barcode: str
    minimum_stock: Decimal
    category_id: int | None
    current_stock: Decimal = Decimal("0.0000")
    operation_kind: str = "PRODUCT_CREATE"


@dataclass(frozen=True, slots=True)
class StockMovementDraft:
    draft_id: str
    fingerprint: str
    operation_kind: str
    product_id: int
    product_code: str
    product_description: str
    amount: Decimal | None
    new_balance: Decimal
    previous_balance: Decimal
    reason: str
    reference: str


class ProductStockDraftService:
    """Prepara somente uma operação por rascunho; jamais persiste."""

    def __init__(self, product_service, *, max_drafts: int = 20) -> None:
        if product_service is None:
            raise ValueError("O serviço oficial de produtos é obrigatório.")
        self._products = product_service
        self._max = max(1, min(int(max_drafts), 100))
        self._drafts = OrderedDict()
        self._lock = Lock()

    def _store(self, draft):
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > self._max:
                self._drafts.popitem(last=False)
        return draft

    def get(self, draft_id: str):
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Rascunho de produto/estoque não encontrado ou descartado.")
        return draft

    def create_product(self, *, code: str = "", description: str, sale_price,
                       cost_price="0", barcode: str = "", minimum_stock="0",
                       category_id: int | None = None) -> ProductCreateDraft:
        command = ProductCreateCommand(
            str(code or "").strip(), str(description or "").strip(), sale_price,
            "MERCADORIA", str(barcode or "").strip(), cost_price,
            Decimal("0"), minimum_stock, False, category_id,
        )
        payload = asdict(command)
        for key, value in tuple(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = format(value, "f")
        draft = ProductCreateDraft(
            uuid4().hex, _fingerprint(payload), command.code, command.description,
            command.sale_price, command.cost_price, command.barcode,
            command.minimum_stock, command.category_id,
        )
        return self._store(draft)

    def create_stock(self, *, operation: str, product_id: int, value,
                     reason: str, reference: str = "") -> StockMovementDraft:
        operation = str(operation or "").strip().upper()
        if operation not in {"STOCK_RECEIVE", "STOCK_REMOVE", "STOCK_ADJUST"}:
            raise ValueError("Operação de estoque não permitida para a Nabi.")
        product = self._products.get_product(int(product_id))
        previous = quantity(product.current_stock, allow_negative=True)
        reason = str(reason or "").strip()
        reference = str(reference or "").strip()
        if operation == "STOCK_ADJUST":
            command = StockAdjustmentCommand(int(product_id), value, reason)
            if command.new_balance < 0:
                raise ValueError("A Nabi não prepara ajuste para saldo negativo.")
            amount = None
            new_balance = command.new_balance
        else:
            command = StockMovementCommand(int(product_id), value, reason, reference)
            amount = command.amount
            new_balance = previous + amount if operation == "STOCK_RECEIVE" else previous - amount
            if new_balance < 0:
                raise ValueError("A Nabi não prepara saída que produza estoque negativo.")
        payload = {
            "operation": operation, "product_id": int(product.product_id),
            "amount": None if amount is None else format(amount, "f"),
            "new_balance": format(new_balance, "f"),
            "previous_balance": format(previous, "f"),
            "reason": reason, "reference": reference,
        }
        return self._store(StockMovementDraft(
            uuid4().hex, _fingerprint(payload), operation, int(product.product_id),
            product.code, product.description, amount, new_balance, previous,
            reason, reference,
        ))
