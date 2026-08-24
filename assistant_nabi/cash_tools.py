from __future__ import annotations

from .contracts import CapabilityLevel, ToolDefinition, ToolKind, ToolRequest, ToolSchema
from commercial.domain.money import MoneyCodec


CASH_CURRENT = ToolDefinition(
    "caixa.consultar_atual",
    ToolKind.READ,
    CapabilityLevel.READ,
    "caixa",
    "view",
    ToolSchema(),
)


class CurrentCashTool:
    def __init__(self, service_factory) -> None:
        self._service_factory = service_factory

    def execute(self, request: ToolRequest, *, actor) -> dict:
        view = self._service_factory(actor).current()
        session = view.session
        return {
            "is_open": view.is_open,
            "session_id": session.id if session is not None else None,
            "opened_at": session.opened_at if session is not None else "",
            "opening_balance": MoneyCodec.canonical(session.opening_balance) if session is not None else "0.00",
            "expected_cash": MoneyCodec.canonical(view.expected_cash),
            "cash_sales": MoneyCodec.canonical(view.cash_sales),
            "pix_sales": MoneyCodec.canonical(view.pix_sales),
            "card_sales": MoneyCodec.canonical(view.card_sales),
            "other_sales": MoneyCodec.canonical(view.other_sales),
            "cash_receipts": MoneyCodec.canonical(view.cash_receipts),
            "supplies": MoneyCodec.canonical(view.supplies),
            "withdrawals": MoneyCodec.canonical(view.withdrawals),
        }


def register_cash_read_tools(registry, service_factory) -> None:
    if service_factory is not None:
        registry.register(CASH_CURRENT, CurrentCashTool(service_factory))
