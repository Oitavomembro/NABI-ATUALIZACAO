from __future__ import annotations

from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.customer_dto import CustomerReceiptCommand

from .confirmations import ConfirmedDraftAuthorization


class NabiCodeCustomerReceiptAssistantGateway:
    """Executa recebimento confirmado pela fachada Commercial oficial."""

    def __init__(self, action_service, customer_service) -> None:
        if action_service is None or customer_service is None:
            raise ValueError("Serviços oficiais de ação e clientes são obrigatórios.")
        self._actions = action_service
        self._customers = customer_service

    def execute(self, draft, authorization):
        if getattr(draft, "operation_kind", "") != "CUSTOMER_RECEIPT":
            raise TypeError("O rascunho não representa recebimento de cliente.")
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("O recebimento exige autorização emitida pelo broker.")
        current = self._customers.get_customer(draft.customer_id)
        if current.debt_balance != draft.previous_balance:
            raise ValueError("O saldo do cliente mudou; prepare e revise um novo recebimento.")
        grant = authorization.consume(draft, operation="CUSTOMER_RECEIPT")
        result = self._actions.receive_customer_payment(
            CustomerReceiptCommand(
                customer_id=draft.customer_id, amount=draft.amount,
                payment_method=draft.payment_method,
                payment_date=draft.payment_date, notes=draft.notes,
            ),
            context=ActionContext(
                requested_by=grant.username, origin=ActionOrigin.AI,
                request_id=draft.draft_id,
            ),
            confirmation_granted=True,
            operation_fingerprint=draft.fingerprint,
        )
        if not result.committed:
            raise ValueError(result.message)
        return result
