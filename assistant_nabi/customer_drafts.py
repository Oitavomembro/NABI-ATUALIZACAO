from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import asdict, dataclass
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from commercial.application.customer_dto import CustomerCreateCommand


@dataclass(frozen=True, slots=True)
class CustomerRegistrationDraft:
    draft_id: str
    fingerprint: str
    name: str
    code: str
    record_number: int
    cpf: str
    rg: str
    phone: str
    address: str
    notes: str
    credit_limit: Decimal
    operation_kind: str = "CUSTOMER_CREATE"


class CustomerRegistrationDraftService:
    """Prepara cadastro revisável sem persistir qualquer dado."""

    def __init__(self, customer_service, *, max_drafts: int = 20) -> None:
        if customer_service is None:
            raise ValueError("O serviço oficial de clientes é obrigatório.")
        self._customers = customer_service
        self._max_drafts = max(1, min(int(max_drafts), 100))
        self._drafts: OrderedDict[str, CustomerRegistrationDraft] = OrderedDict()
        self._lock = Lock()

    def create(self, **values) -> CustomerRegistrationDraft:
        record_number = values.get("record_number")
        if record_number in (None, ""):
            record_number = self._customers.next_record_number()
        command = CustomerCreateCommand(
            name=str(values.get("name") or "").strip(),
            code=str(values.get("code") or "").strip(),
            record_number=int(record_number),
            cpf=str(values.get("cpf") or "").strip(),
            rg=str(values.get("rg") or "").strip(),
            phone=str(values.get("phone") or "").strip(),
            address=str(values.get("address") or "").strip(),
            notes=str(values.get("notes") or "").strip(),
            credit_limit=values.get("credit_limit", "0.00"),
        )
        if not command.name:
            raise ValueError("O nome do cliente é obrigatório.")
        if command.record_number is None or int(command.record_number) <= 0:
            raise ValueError("A ficha do cliente é obrigatória.")
        payload = asdict(command)
        payload["credit_limit"] = format(command.credit_limit, "f")
        fingerprint = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        draft = CustomerRegistrationDraft(
            uuid4().hex, fingerprint, command.name, command.code,
            int(command.record_number), command.cpf, command.rg, command.phone,
            command.address, command.notes, command.credit_limit,
        )
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > self._max_drafts:
                self._drafts.popitem(last=False)
        return draft

    def get(self, draft_id: str) -> CustomerRegistrationDraft:
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Rascunho de cliente não encontrado ou descartado.")
        return draft
