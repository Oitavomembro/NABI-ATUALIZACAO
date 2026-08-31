from __future__ import annotations

from collections.abc import Callable

from .action_dto import ActionContext, ActionSensitivity
from .financial_dto import (
    CreateFinancialTitleCommand, FinancialActionResult, FinancialEvent,
    SettleFinancialTitleCommand,
)
from .ports import FinancialActionPort, FinancialEventPort


class FinancialActionService:
    """Única fachada para mutações financeiras expostas fora do backend."""

    def __init__(
        self, gateway: FinancialActionPort, events: FinancialEventPort | None = None,
        mutation_authorizer: Callable[[str, str], str] | None = None,
    ) -> None:
        self._gateway = gateway
        self._events = events
        self._mutation_authorizer = mutation_authorizer

    def bind_mutation_authorizer(self, authorizer: Callable[[str, str], str]) -> None:
        if not callable(authorizer):
            raise TypeError("A porta de autorização do Financeiro deve ser chamável.")
        self._mutation_authorizer = authorizer

    def _authorize_mutation(self, action: str, context: ActionContext) -> ActionContext:
        if self._mutation_authorizer is None:
            return context
        actor = str(self._mutation_authorizer("financeiro", action) or "").strip()
        if not actor:
            raise PermissionError("Sessão autenticada inválida para o Financeiro.")
        return ActionContext(
            requested_by=actor, origin=context.origin,
            requested_at=context.requested_at, request_id=context.request_id,
        )

    def _run(self, action, permission, context, sensitivity, confirmed, operation, event_kind):
        required = True
        if not confirmed:
            return FinancialActionResult(action, context, sensitivity, required, False, False, "Confirmação humana obrigatória.")
        try:
            context = self._authorize_mutation(permission, context)
        except PermissionError as exc:
            return FinancialActionResult(
                action, context, sensitivity, required, False, False, str(exc)
            )
        try:
            persisted = operation(context.requested_by)
        except (ValueError, LookupError) as exc:
            return FinancialActionResult(action, context, sensitivity, required, False, False, str(exc))
        secondary_failed = False
        if self._events and not persisted.idempotent_replay:
            try:
                self._events.financial_event(FinancialEvent(event_kind, persisted.title_id, context, persisted.payment_id))
            except Exception:
                secondary_failed = True
        message = "Operação financeira confirmada."
        if secondary_failed:
            message += " A notificação posterior falhou; não repita a operação."
        return FinancialActionResult(
            action, context, sensitivity, required, True, True, message,
            persisted.title_id, persisted.payment_id, persisted.status,
            persisted.open_amount, secondary_failed,
        )

    def create_receivable(self, command: CreateFinancialTitleCommand, *, context: ActionContext, confirmed: bool, operation_fingerprint: str | None = None):
        return self._run("CREATE_RECEIVABLE", "create", context, ActionSensitivity.SENSITIVE, confirmed,
                         lambda actor: self._gateway.create_title("RECEBER", command, user=actor, idempotency_key=f"nabi:financial:{context.request_id}" if operation_fingerprint else None, operation_fingerprint=operation_fingerprint), "RECEIVABLE_CREATED")

    def create_payable(self, command: CreateFinancialTitleCommand, *, context: ActionContext, confirmed: bool, operation_fingerprint: str | None = None):
        return self._run("CREATE_PAYABLE", "create", context, ActionSensitivity.SENSITIVE, confirmed,
                         lambda actor: self._gateway.create_title("PAGAR", command, user=actor, idempotency_key=f"nabi:financial:{context.request_id}" if operation_fingerprint else None, operation_fingerprint=operation_fingerprint), "PAYABLE_CREATED")

    def settle_receivable(self, command: SettleFinancialTitleCommand, *, context: ActionContext, confirmed: bool, operation_fingerprint: str | None = None):
        return self._run("SETTLE_RECEIVABLE", "pay", context, ActionSensitivity.SENSITIVE, confirmed,
                         lambda actor: self._gateway.settle("RECEBER", command, user=actor, idempotency_key=f"nabi:financial:{context.request_id}" if operation_fingerprint else None, operation_fingerprint=operation_fingerprint), "RECEIVABLE_SETTLED")

    def settle_payable(self, command: SettleFinancialTitleCommand, *, context: ActionContext, confirmed: bool, operation_fingerprint: str | None = None):
        return self._run("SETTLE_PAYABLE", "pay", context, ActionSensitivity.SENSITIVE, confirmed,
                         lambda actor: self._gateway.settle("PAGAR", command, user=actor, idempotency_key=f"nabi:financial:{context.request_id}" if operation_fingerprint else None, operation_fingerprint=operation_fingerprint), "PAYABLE_SETTLED")

    def cancel_financial_title(self, title_id: int, *, context: ActionContext, confirmed: bool):
        return self._run("CANCEL_FINANCIAL_TITLE", "reconcile", context, ActionSensitivity.CRITICAL, confirmed,
                         lambda actor: self._gateway.cancel(title_id, user=actor), "FINANCIAL_TITLE_CANCELLED")

    def reverse_financial_payment(self, payment_id: int, *, context: ActionContext, confirmed: bool):
        return self._run("REVERSE_FINANCIAL_PAYMENT", "reconcile", context, ActionSensitivity.CRITICAL, confirmed,
                         lambda actor: self._gateway.reverse_payment(payment_id, user=actor), "FINANCIAL_PAYMENT_REVERSED")
