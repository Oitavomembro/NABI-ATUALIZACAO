from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from commercial.domain.money import MoneyCodec
from services.cash_service import CashSession


@dataclass(frozen=True, slots=True)
class CashMovementView:
    occurred_at: str
    movement_type: str
    amount: Decimal
    user: str
    note: str
    sign: int


@dataclass(frozen=True, slots=True)
class CashSessionView:
    session: CashSession | None
    expected_cash: Decimal
    cash_sales: Decimal
    pix_sales: Decimal
    card_sales: Decimal
    other_sales: Decimal
    cash_receipts: Decimal
    supplies: Decimal
    withdrawals: Decimal
    documented_outflows: Decimal
    movements: tuple[CashMovementView, ...]

    @property
    def is_open(self) -> bool:
        return self.session is not None and self.session.status == "ABERTO"


@dataclass(frozen=True, slots=True)
class DocumentedOutflowDraft:
    payload: Mapping[str, Any]
    fingerprint: str


class CashApplicationService:
    """Porta operacional do Caixa: fixa terminal/ator fora da GUI."""

    def __init__(self, cash_service, *, terminal: str, user: str = "", security=None) -> None:
        self._cash = cash_service
        self._security = security
        self.terminal = str(terminal or "").strip()
        self.user = str(user or "").strip()
        if not self.terminal:
            raise ValueError("Terminal do caixa é obrigatório.")
        if not self.user and self._security is None:
            raise ValueError("Usuário ou sessão do caixa é obrigatório.")

    def _authenticated_actor(self) -> str:
        security = self._security
        session = getattr(security, "session", None) if security is not None else None
        if security is None or session is None or security.is_expired():
            raise PermissionError("Sessão autenticada é obrigatória para fechar o caixa.")
        if not security.require("financeiro", "view"):
            raise PermissionError("Seu perfil não possui permissão para fechar o caixa.")
        user = getattr(session, "user", None)
        actor = str(getattr(user, "username", "") or "").strip()
        if not actor:
            raise PermissionError("A sessão não possui operador identificado.")
        security.touch()
        return actor

    def current(self) -> CashSessionView:
        session = self._cash.get_open_session(self.terminal)
        if session is None:
            return CashSessionView(
                None, *(MoneyCodec.ZERO for _ in range(9)), movements=()
            )
        summary = self._cash.session_summary(session.id)
        movements = tuple(CashMovementView(
            occurred_at=str(item.get("data") or ""),
            movement_type=str(item.get("tipo") or ""),
            amount=MoneyCodec.parse(item.get("valor") or 0),
            user=str(item.get("usuario") or ""), note=str(item.get("observacao") or ""),
            sign=-1 if int(item.get("sinal", 1)) < 0 else 1,
        ) for item in summary["movements"])
        return CashSessionView(
            session=session, expected_cash=MoneyCodec.parse(summary["expected_cash"]),
            cash_sales=MoneyCodec.parse(summary["dinheiro"]),
            pix_sales=MoneyCodec.parse(summary["pix"]),
            card_sales=MoneyCodec.parse(summary["cartao"]),
            other_sales=MoneyCodec.parse(summary["outros"]),
            cash_receipts=MoneyCodec.parse(summary["recebimentos_dinheiro"]),
            supplies=MoneyCodec.parse(summary["suprimentos"]),
            withdrawals=MoneyCodec.parse(summary["sangrias"]),
            documented_outflows=MoneyCodec.parse(summary.get("documented_outflows", 0)), movements=movements,
        )

    def open(self, opening_balance=Decimal("0"), *, informed: bool = True) -> CashSessionView:
        self._cash.open_session(
            self.terminal, self.user, opening_balance,
            "VALOR_INFORMADO" if informed else "SEM_VALOR_INFORMADO",
        )
        return self.current()

    def register_movement(self, movement_type: str, amount, note: str = "") -> CashSessionView:
        self._cash.register_session_movement(
            self.terminal, movement_type, amount, self.user, note
        )
        return self.current()

    def prepare_documented_outflow(self, **fields: Any) -> DocumentedOutflowDraft:
        fields.setdefault("occurred_on", date.today().isoformat())
        fields.setdefault("competence", str(fields["occurred_on"])[:7])
        normalized = self._cash.normalize_documented_outflow(fields)
        return DocumentedOutflowDraft(
            MappingProxyType(dict(normalized)),
            self._cash.documented_outflow_fingerprint(normalized),
        )

    def confirm_documented_outflow(
        self, draft: DocumentedOutflowDraft, *, idempotency_key: str = "",
    ) -> int:
        actor = self._authorized_actor("create", "registrar uma saída documentada")
        key = str(idempotency_key or f"cash-outflow:{uuid4().hex}")
        return self._cash.register_documented_outflow(
            self.terminal, dict(draft.payload), user=actor,
            idempotency_key=key, fingerprint=draft.fingerprint,
        )

    def _authorized_actor(self, action: str, operation: str) -> str:
        security = self._security
        session = getattr(security, "session", None) if security is not None else None
        if security is None or session is None or security.is_expired():
            raise PermissionError(f"Sessão autenticada é obrigatória para {operation}.")
        if not security.require("financeiro", action):
            raise PermissionError(f"Seu perfil não possui permissão para {operation}.")
        actor = str(getattr(getattr(session, "user", None), "username", "") or "").strip()
        if not actor: raise PermissionError("A sessão não possui operador identificado.")
        security.touch(); return actor

    def close(self, counted_cash, note: str = "") -> CashSession:
        return self._cash.close_session(
            self.terminal, counted_cash, self._authenticated_actor(), note
        )

    def history(self) -> tuple[CashSession, ...]:
        return tuple(self._cash.history(self.terminal))
