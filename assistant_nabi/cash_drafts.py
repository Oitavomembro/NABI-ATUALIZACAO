from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from commercial.domain.money import MoneyCodec


@dataclass(frozen=True, slots=True)
class CashDraft:
    draft_id: str
    fingerprint: str
    operation_kind: str
    terminal: str
    amount: Decimal
    note: str = ""
    opening_mode: str = ""
    expected_session_id: int | None = None


class CashDraftService:
    """Prepara operações de caixa sem executar ou acessar persistência."""

    def __init__(self, state_gateway, *, max_drafts: int = 20) -> None:
        self._state = state_gateway
        self._drafts = OrderedDict(); self._lock = Lock()
        self._max = max(1, min(int(max_drafts), 100))

    def _store(self, operation, *, terminal, amount, note="", opening_mode="", session_id=None):
        payload = {"operation": operation, "terminal": terminal,
                   "amount": format(amount, ".2f"), "note": note,
                   "opening_mode": opening_mode, "session_id": session_id}
        fingerprint = hashlib.sha256(json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest()
        draft = CashDraft(uuid4().hex, fingerprint, operation, terminal, amount,
                          note, opening_mode, session_id)
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > self._max: self._drafts.popitem(last=False)
        return draft

    def prepare_open(self, *, opening_balance=0, informed=True):
        current = self._state.current()
        if current.is_open: raise ValueError("Já existe caixa aberto neste terminal.")
        amount = MoneyCodec.parse(opening_balance, field="saldo inicial")
        if amount < 0: raise ValueError("O saldo inicial não pode ser negativo.")
        mode = "VALOR_INFORMADO" if informed else "SEM_VALOR_INFORMADO"
        if not informed: amount = MoneyCodec.ZERO
        return self._store("CASH_OPEN", terminal=self._state.terminal,
                           amount=amount, opening_mode=mode)

    def prepare_movement(self, *, movement_type, amount, note=""):
        current = self._state.current()
        if not current.is_open: raise RuntimeError("Não existe caixa aberto neste terminal.")
        kind = str(movement_type or "").strip().upper()
        if kind not in {"SANGRIA", "SUPRIMENTO"}: raise ValueError("Movimento inválido.")
        value = MoneyCodec.parse(amount, field="valor do movimento")
        if value <= 0: raise ValueError("O valor deve ser maior que zero.")
        return self._store(f"CASH_{kind}", terminal=self._state.terminal,
                           amount=value, note=str(note or "").strip(),
                           session_id=current.session.id)

    def prepare_close(self, *, counted_cash, note=""):
        current = self._state.current()
        if not current.is_open: raise RuntimeError("Não existe caixa aberto neste terminal.")
        value = MoneyCodec.parse(counted_cash, field="valor contado")
        if value < 0: raise ValueError("O valor contado não pode ser negativo.")
        return self._store("CASH_CLOSE", terminal=self._state.terminal,
                           amount=value, note=str(note or "").strip(),
                           session_id=current.session.id)

    def get(self, draft_id):
        with self._lock: draft = self._drafts.get(str(draft_id or ""))
        if draft is None: raise ValueError("Rascunho de caixa não encontrado.")
        return draft
