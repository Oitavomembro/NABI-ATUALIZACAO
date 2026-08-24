from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from commercial.domain.money import MoneyCodec


PAYMENT_METHODS = frozenset({"DINHEIRO", "PIX", "DEBITO", "CREDITO", "OUTROS"})


@dataclass(frozen=True, slots=True)
class CustomerReceiptDraft:
    draft_id: str
    fingerprint: str
    customer_id: int
    record_number: int | None
    customer_name: str
    amount: Decimal
    previous_balance: Decimal
    expected_balance: Decimal
    payment_method: str
    payment_date: date
    notes: str
    operation_kind: str = "CUSTOMER_RECEIPT"


class CustomerReceiptDraftService:
    """Prepara recebimento sem alterar saldo, parcelas, caixa ou financeiro."""

    def __init__(self, customer_service, *, max_drafts: int = 20) -> None:
        if customer_service is None:
            raise ValueError("O serviço oficial de clientes é obrigatório.")
        self._customers = customer_service
        self._max_drafts = max(1, min(int(max_drafts), 100))
        self._drafts: OrderedDict[str, CustomerReceiptDraft] = OrderedDict()
        self._lock = Lock()

    def create(
        self, *, customer_id: int, amount, payment_method: str,
        payment_date: str, notes: str = "",
    ) -> CustomerReceiptDraft:
        customer = self._customers.get_customer(int(customer_id))
        value = MoneyCodec.parse(amount, field="valor recebido")
        balance = MoneyCodec.parse(customer.debt_balance, field="saldo devedor")
        if value <= 0 or balance <= 0:
            raise ValueError("Cliente sem saldo ou valor de recebimento inválido.")
        if value > balance:
            raise ValueError("O recebimento não pode ultrapassar o saldo do cliente.")
        method = str(payment_method or "").strip().upper()
        if method not in PAYMENT_METHODS:
            raise ValueError("Forma de pagamento não permitida para o recebimento.")
        try:
            paid_on = date.fromisoformat(str(payment_date or ""))
        except ValueError as error:
            raise ValueError("Data do recebimento deve estar em AAAA-MM-DD.") from error
        note = str(notes or "").strip()
        expected = (balance - value).quantize(Decimal("0.01"))
        payload = {
            "customer_id": int(customer.customer_id),
            "record_number": customer.record_number,
            "amount": format(value, "f"),
            "previous_balance": format(balance, "f"),
            "expected_balance": format(expected, "f"),
            "payment_method": method,
            "payment_date": paid_on.isoformat(),
            "notes": note,
        }
        fingerprint = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        draft = CustomerReceiptDraft(
            uuid4().hex, fingerprint, int(customer.customer_id),
            customer.record_number, customer.name, value, balance, expected,
            method, paid_on, note,
        )
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > self._max_drafts:
                self._drafts.popitem(last=False)
        return draft

    def get(self, draft_id: str) -> CustomerReceiptDraft:
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Rascunho de recebimento não encontrado ou descartado.")
        return draft
