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


@dataclass(frozen=True, slots=True)
class FinancialDraft:
    draft_id: str
    fingerprint: str
    operation_kind: str
    title_type: str
    amount: Decimal
    due_date: date | None = None
    title_id: int | None = None
    party_id: int | None = None
    party_name: str = ""
    document: str = ""
    description: str = ""
    notes: str = ""
    issue_date: date | None = None
    payment_method: str = ""
    payment_date: date | None = None
    previous_open_amount: Decimal | None = None
    expected_open_amount: Decimal | None = None


class FinancialDraftService:
    """Prepara títulos e baixas sem alterar o Financeiro."""

    def __init__(self, gateway, *, max_drafts: int = 20) -> None:
        if gateway is None:
            raise ValueError("A porta financeira oficial é obrigatória.")
        self._gateway = gateway
        self._max_drafts = max(1, min(int(max_drafts), 100))
        self._drafts: OrderedDict[str, FinancialDraft] = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def _type(value: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in {"RECEBER", "PAGAR"}:
            raise ValueError("Tipo financeiro deve ser RECEBER ou PAGAR.")
        return normalized

    @staticmethod
    def _date(value, field: str) -> date:
        try:
            return value if isinstance(value, date) else date.fromisoformat(str(value or ""))
        except ValueError as error:
            raise ValueError(f"{field} deve estar em AAAA-MM-DD.") from error

    def _store(self, payload: dict, **values) -> FinancialDraft:
        fingerprint = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        draft = FinancialDraft(uuid4().hex, fingerprint, **values)
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > self._max_drafts:
                self._drafts.popitem(last=False)
        return draft

    def create_title(self, *, title_type: str, amount, due_date: str,
                     party_id: int | None = None, party_name: str = "",
                     document: str = "", description: str = "", notes: str = "",
                     issue_date: str | None = None) -> FinancialDraft:
        kind = self._type(title_type)
        value = MoneyCodec.parse(amount, field="valor do título")
        if value <= 0:
            raise ValueError("O valor do título deve ser maior que zero.")
        due = self._date(due_date, "Vencimento")
        issued = self._date(issue_date, "Emissão") if issue_date else None
        party = None if party_id is None else int(party_id)
        if party is not None and party <= 0:
            raise ValueError("Identificação da pessoa inválida.")
        payload = {
            "operation": f"FINANCIAL_CREATE_{kind}", "title_type": kind,
            "amount": format(value, "f"), "due_date": due.isoformat(),
            "party_id": party, "party_name": str(party_name or "").strip(),
            "document": str(document or "").strip(),
            "description": str(description or "").strip(),
            "notes": str(notes or "").strip(),
            "issue_date": issued.isoformat() if issued else None,
        }
        return self._store(payload, operation_kind=payload["operation"],
                           title_type=kind, amount=value, due_date=due,
                           party_id=party, party_name=payload["party_name"],
                           document=payload["document"], description=payload["description"],
                           notes=payload["notes"], issue_date=issued)

    def settle_title(self, *, title_type: str, title_id: int, amount,
                     payment_method: str, payment_date: str, notes: str = "") -> FinancialDraft:
        kind = self._type(title_type)
        title = self._gateway.get_title(int(title_id))
        if title is None or str(title.get("tipo") or "").upper() != kind:
            raise ValueError(f"Título {kind} não encontrado.")
        if str(title.get("status") or "").upper() not in {"ABERTO", "PARCIAL"}:
            raise ValueError("O título não aceita baixa.")
        value = MoneyCodec.parse(amount, field="valor da baixa")
        current = MoneyCodec.parse(title["saldo_aberto"], field="saldo aberto")
        if value <= 0 or value > current:
            raise ValueError("A baixa deve ser positiva e não pode ultrapassar o saldo aberto.")
        method = str(payment_method or "").strip().upper()
        if method not in self._gateway.payment_methods:
            raise ValueError("Forma de pagamento financeira inválida.")
        paid_on = self._date(payment_date, "Data da baixa")
        expected = (current - value).quantize(Decimal("0.01"))
        payload = {
            "operation": f"FINANCIAL_SETTLE_{kind}", "title_type": kind,
            "title_id": int(title_id), "amount": format(value, "f"),
            "previous_open_amount": format(current, "f"),
            "expected_open_amount": format(expected, "f"),
            "payment_method": method, "payment_date": paid_on.isoformat(),
            "notes": str(notes or "").strip(),
        }
        return self._store(payload, operation_kind=payload["operation"],
                           title_type=kind, title_id=int(title_id), amount=value,
                           payment_method=method, payment_date=paid_on,
                           previous_open_amount=current, expected_open_amount=expected,
                           notes=payload["notes"])

    def get(self, draft_id: str) -> FinancialDraft:
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Rascunho financeiro não encontrado ou descartado.")
        return draft
