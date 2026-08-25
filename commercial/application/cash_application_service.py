from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

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
    movements: tuple[CashMovementView, ...]

    @property
    def is_open(self) -> bool:
        return self.session is not None and self.session.status == "ABERTO"


class CashApplicationService:
    """Porta operacional do Caixa: fixa terminal/ator fora da GUI."""

    def __init__(self, cash_service, *, terminal: str, user: str) -> None:
        self._cash = cash_service
        self.terminal = str(terminal or "").strip()
        self.user = str(user or "").strip()
        if not self.terminal or not self.user:
            raise ValueError("Terminal e usuário do caixa são obrigatórios.")

    def current(self) -> CashSessionView:
        session = self._cash.get_open_session(self.terminal)
        if session is None:
            return CashSessionView(
                None, *(MoneyCodec.ZERO for _ in range(8)), movements=()
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
            withdrawals=MoneyCodec.parse(summary["sangrias"]), movements=movements,
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

    def close(self, counted_cash, note: str = "") -> CashSession:
        return self._cash.close_session(
            self.terminal, counted_cash, self.user, note
        )

    def history(self) -> tuple[CashSession, ...]:
        return tuple(self._cash.history(self.terminal))

    def open_assisted(self, opening_balance, opening_mode, *, username,
                      idempotency_key, operation_fingerprint):
        if str(username or "").strip() != self.user:
            raise PermissionError("O operador confirmado não corresponde à sessão do caixa.")
        return self._cash.open_session_assisted(
            self.terminal, self.user, opening_balance, opening_mode,
            idempotency_key=idempotency_key,
            operation_fingerprint=operation_fingerprint,
        )

    def movement_assisted(self, movement_type, amount, note, *, username,
                          idempotency_key, operation_fingerprint):
        if str(username or "").strip() != self.user:
            raise PermissionError("O operador confirmado não corresponde à sessão do caixa.")
        return self._cash.register_session_movement_assisted(
            self.terminal, movement_type, amount, self.user, note,
            idempotency_key=idempotency_key,
            operation_fingerprint=operation_fingerprint,
        )

    def close_assisted(self, counted_cash, note, *, username,
                       idempotency_key, operation_fingerprint):
        if str(username or "").strip() != self.user:
            raise PermissionError("O operador confirmado não corresponde à sessão do caixa.")
        return self._cash.close_session_assisted(
            self.terminal, counted_cash, self.user, note,
            idempotency_key=idempotency_key,
            operation_fingerprint=operation_fingerprint,
        )
