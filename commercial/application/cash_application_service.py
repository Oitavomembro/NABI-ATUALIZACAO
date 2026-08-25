from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from math import ceil
from typing import Callable

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
    origin: str = ""
    document: str = ""


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


class CashDetailKind(str, Enum):
    EXPECTED = "expected"
    CASH_SALES = "cash"
    PIX_SALES = "pix"
    CARD_SALES = "card"
    SUPPLIES = "supplies"
    WITHDRAWALS = "withdrawals"


_DETAIL_LABELS = {
    CashDetailKind.EXPECTED: "DINHEIRO ESPERADO",
    CashDetailKind.CASH_SALES: "VENDAS DINHEIRO",
    CashDetailKind.PIX_SALES: "PIX",
    CashDetailKind.CARD_SALES: "CARTÃO",
    CashDetailKind.SUPPLIES: "SUPRIMENTOS",
    CashDetailKind.WITHDRAWALS: "SANGRIAS",
}


@dataclass(frozen=True, slots=True)
class CashDetailRow:
    occurred_at: str
    origin: str
    movement_type: str
    amount: Decimal
    direction: str
    responsible: str = ""
    document: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", MoneyCodec.parse(self.amount))
        if self.direction not in {"ENTRADA", "SAÍDA"}:
            raise ValueError("A direção do detalhe deve ser ENTRADA ou SAÍDA.")


@dataclass(frozen=True, slots=True)
class CashDetailPage:
    kind: CashDetailKind
    label: str
    session_id: int | None
    period_start: str
    period_end: str
    card_total: Decimal
    detail_total: Decimal
    reconciled: bool
    page: int
    page_size: int
    total_pages: int
    total_items: int
    items: tuple[CashDetailRow, ...]


@dataclass(frozen=True, slots=True)
class CashDetailSnapshot:
    kind: CashDetailKind
    label: str
    session_id: int | None
    period_start: str
    period_end: str
    card_total: Decimal
    detail_total: Decimal
    reconciled: bool
    items: tuple[CashDetailRow, ...]

    def page(self, page: int, *, page_size: int = 50) -> CashDetailPage:
        page = int(page)
        page_size = int(page_size)
        if page < 1:
            raise ValueError("A página deve ser maior que zero.")
        if not 1 <= page_size <= 100:
            raise ValueError("A página deve conter entre 1 e 100 lançamentos.")
        total_items = len(self.items)
        total_pages = max(1, ceil(total_items / page_size))
        if page > total_pages:
            raise ValueError("A página solicitada não existe neste detalhamento.")
        start = (page - 1) * page_size
        return CashDetailPage(
            self.kind, self.label, self.session_id, self.period_start,
            self.period_end, self.card_total, self.detail_total, self.reconciled,
            page, page_size, total_pages, total_items,
            self.items[start:start + page_size],
        )


class CashApplicationService:
    """Porta operacional do Caixa: fixa terminal/ator fora da GUI."""

    def __init__(
        self, cash_service, *, terminal: str, user: str,
        actor_provider: Callable[[str], str] | None = None,
    ) -> None:
        self._cash = cash_service
        self.terminal = str(terminal or "").strip()
        self.user = str(user or "").strip()
        self._actor_provider = actor_provider
        if not self.terminal or not self.user:
            raise ValueError("Terminal e usuário do caixa são obrigatórios.")

    def _authorized_actor(self, action: str) -> str:
        if self._actor_provider is None:
            return self.user
        actor = str(self._actor_provider(action) or "").strip()
        if not actor:
            raise PermissionError("Sessão ativa e permissão do Caixa são obrigatórias.")
        return actor

    def _current(self) -> CashSessionView:
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
            origin=str(item.get("origem") or ""),
            document=str(item.get("documento") or ""),
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

    def current(self) -> CashSessionView:
        self._authorized_actor("view")
        return self._current()

    @staticmethod
    def _detail_row(movement: CashMovementView, *, signed: bool) -> CashDetailRow:
        amount = movement.amount * movement.sign if signed else movement.amount
        return CashDetailRow(
            occurred_at=movement.occurred_at,
            origin=movement.origin,
            movement_type=movement.movement_type,
            amount=amount,
            direction="SAÍDA" if movement.sign < 0 else "ENTRADA",
            responsible=movement.user,
            document=movement.document,
            note=movement.note,
        )

    def detail_snapshot(self, kind: CashDetailKind | str) -> CashDetailSnapshot:
        """Cria uma prova imutável e paginável a partir do resumo oficial do Caixa."""

        selected = kind if isinstance(kind, CashDetailKind) else CashDetailKind(str(kind))
        state = self.current()
        session = state.session
        rows: list[CashDetailRow] = []

        if selected is CashDetailKind.EXPECTED and session is not None:
            rows.append(CashDetailRow(
                occurred_at=str(session.opened_at or ""),
                origin=f"ABERTURA DO CAIXA #{int(session.id)}",
                movement_type="SALDO INICIAL",
                amount=session.opening_balance,
                direction="ENTRADA",
                responsible=str(session.opened_by or ""),
                note=str(session.opening_mode or ""),
            ))

        accepted_types = {
            CashDetailKind.EXPECTED: {
                "VENDA DINHEIRO", "RECEBIMENTO DINHEIRO", "SUPRIMENTO", "SANGRIA",
            },
            CashDetailKind.CASH_SALES: {"VENDA DINHEIRO"},
            CashDetailKind.PIX_SALES: {"VENDA PIX"},
            CashDetailKind.CARD_SALES: {"VENDA CARTAO", "VENDA CARTÃO"},
            CashDetailKind.SUPPLIES: {"SUPRIMENTO"},
            CashDetailKind.WITHDRAWALS: {"SANGRIA"},
        }[selected]
        for movement in state.movements:
            if movement.movement_type.strip().upper() in accepted_types:
                rows.append(self._detail_row(
                    movement, signed=selected is CashDetailKind.EXPECTED,
                ))

        card_total = {
            CashDetailKind.EXPECTED: state.expected_cash,
            CashDetailKind.CASH_SALES: state.cash_sales,
            CashDetailKind.PIX_SALES: state.pix_sales,
            CashDetailKind.CARD_SALES: state.card_sales,
            CashDetailKind.SUPPLIES: state.supplies,
            CashDetailKind.WITHDRAWALS: state.withdrawals,
        }[selected]
        detail_total = sum((row.amount for row in rows), MoneyCodec.ZERO)
        card_total = MoneyCodec.parse(card_total)
        detail_total = MoneyCodec.parse(detail_total)
        return CashDetailSnapshot(
            selected, _DETAIL_LABELS[selected], int(session.id) if session else None,
            str(session.opened_at or "") if session else "",
            str(session.closed_at or "") if session else "",
            card_total, detail_total, card_total == detail_total, tuple(rows),
        )

    def open(self, opening_balance=Decimal("0"), *, informed: bool = True) -> CashSessionView:
        actor = self._authorized_actor("create")
        self._cash.open_session(
            self.terminal, actor, opening_balance,
            "VALOR_INFORMADO" if informed else "SEM_VALOR_INFORMADO",
        )
        return self._current()

    def register_movement(self, movement_type: str, amount, note: str = "") -> CashSessionView:
        actor = self._authorized_actor("create")
        self._cash.register_session_movement(
            self.terminal, movement_type, amount, actor, note
        )
        return self._current()

    def close(self, counted_cash, note: str = "") -> CashSession:
        actor = self._authorized_actor("reconcile")
        return self._cash.close_session(
            self.terminal, counted_cash, actor, note
        )

    def history(self) -> tuple[CashSession, ...]:
        self._authorized_actor("view")
        return tuple(self._cash.history(self.terminal))
