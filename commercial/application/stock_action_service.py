from __future__ import annotations

from .action_dto import ActionContext, ActionSensitivity
from .ports import StockActionPort, StockEventPort
from .product_dto import StockActionResult, StockEvent


class StockActionService:
    def __init__(self, gateway: StockActionPort, events: StockEventPort | None = None) -> None:
        self._gateway = gateway
        self._events = events

    def _run(self, action, context, sensitivity, confirmed, operation, event_kind):
        if not confirmed:
            return StockActionResult(action, context, sensitivity, True, False, False, "Confirmação humana obrigatória.")
        try:
            persisted = operation()
        except (ValueError, LookupError) as exc:
            return StockActionResult(action, context, sensitivity, True, False, False, str(exc))
        secondary_failed = False
        if self._events:
            try:
                self._events.stock_event(StockEvent(event_kind, persisted.movement_id, persisted.product_id, context))
            except Exception:
                secondary_failed = True
        message = "Movimentação de estoque confirmada."
        if secondary_failed:
            message += " A notificação posterior falhou; não repita a operação."
        return StockActionResult(
            action, context, sensitivity, True, True, True, message,
            persisted.movement_id, persisted.product_id, persisted.resulting_balance,
            secondary_failed,
        )

    def receive_stock(self, command, *, context: ActionContext, confirmed: bool):
        return self._run("RECEIVE_STOCK", context, ActionSensitivity.SENSITIVE, confirmed,
                         lambda: self._gateway.receive(command, user=context.requested_by), "STOCK_RECEIVED")

    def remove_stock(self, command, *, context: ActionContext, confirmed: bool):
        return self._run("REMOVE_STOCK", context, ActionSensitivity.SENSITIVE, confirmed,
                         lambda: self._gateway.remove(command, user=context.requested_by), "STOCK_REMOVED")

    def adjust_stock(self, command, *, context: ActionContext, confirmed: bool):
        return self._run("ADJUST_STOCK", context, ActionSensitivity.CRITICAL, confirmed,
                         lambda: self._gateway.adjust(command, user=context.requested_by), "STOCK_ADJUSTED")
