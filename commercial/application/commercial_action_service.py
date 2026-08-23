from __future__ import annotations

from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.pdv_session import PDVSession

from .action_dto import (
    ActionContext, ActionSensitivity, CommercialActionResult, SaleCancelled,
)
from .ports import CommercialActionEventPort, SaleCancellationPort
from .customer_dto import CustomerPaymentReceived, CustomerReceiptCommand
from .ports import CustomerReceiptPort


class CommercialActionService:
    """Fachada única para mutações comerciais expostas a adaptadores externos."""

    def __init__(
        self,
        *,
        pdv: PDVApplicationService,
        cancellation: SaleCancellationPort,
        events: CommercialActionEventPort | None = None,
        customer_receipts: CustomerReceiptPort | None = None,
    ) -> None:
        self._pdv = pdv
        self._cancellation = cancellation
        self._events = events
        self._customer_receipts = customer_receipts

    @staticmethod
    def _confirmation_required(
        action: str, context: ActionContext, sensitivity: ActionSensitivity
    ) -> CommercialActionResult:
        return CommercialActionResult(
            action=action,
            context=context,
            sensitivity=sensitivity,
            requires_human_confirmation=True,
            executed=False,
            committed=False,
            message="A ação exige confirmação humana explícita.",
        )

    def checkout(
        self,
        session: PDVSession,
        *,
        context: ActionContext,
        confirmation_granted: bool,
    ) -> CommercialActionResult:
        sensitivity = ActionSensitivity.CRITICAL
        if not confirmation_granted:
            return self._confirmation_required("FINALIZAR_VENDA", context, sensitivity)
        result = self._pdv.checkout(session, user=context.requested_by)
        return CommercialActionResult(
            action="FINALIZAR_VENDA",
            context=context,
            sensitivity=sensitivity,
            requires_human_confirmation=True,
            executed=True,
            committed=result.committed,
            message=result.message,
            resource_id=result.sale_id,
            secondary_effect_failed=result.secondary_effect_failed,
        )

    def cancel_sale(
        self,
        sale_id: int,
        *,
        context: ActionContext,
        confirmation_granted: bool,
    ) -> CommercialActionResult:
        sensitivity = ActionSensitivity.SENSITIVE
        if not confirmation_granted:
            return self._confirmation_required("CANCELAR_VENDA", context, sensitivity)
        try:
            persisted = self._cancellation.cancel(sale_id, user=context.requested_by)
        except Exception as error:
            message = str(error) if isinstance(error, ValueError) else "Não foi possível cancelar a venda."
            return CommercialActionResult(
                action="CANCELAR_VENDA",
                context=context,
                sensitivity=sensitivity,
                requires_human_confirmation=True,
                executed=True,
                committed=False,
                message=message,
            )

        event_failed = False
        if self._events is not None:
            try:
                self._events.sale_cancelled(SaleCancelled(persisted.sale_id, context))
            except Exception:
                event_failed = True
        message = f"Venda #{persisted.sale_id} cancelada."
        if event_failed:
            message += " Um efeito secundário falhou; não repita o cancelamento."
        return CommercialActionResult(
            action="CANCELAR_VENDA",
            context=context,
            sensitivity=sensitivity,
            requires_human_confirmation=True,
            executed=True,
            committed=True,
            message=message,
            resource_id=persisted.sale_id,
            secondary_effect_failed=event_failed,
        )

    def receive_customer_payment(
        self,
        command: CustomerReceiptCommand,
        *,
        context: ActionContext,
        confirmation_granted: bool,
    ) -> CommercialActionResult:
        sensitivity = ActionSensitivity.SENSITIVE
        if not confirmation_granted:
            return self._confirmation_required("RECEBER_PAGAMENTO_CLIENTE", context, sensitivity)
        if self._customer_receipts is None:
            return CommercialActionResult(
                action="RECEBER_PAGAMENTO_CLIENTE", context=context,
                sensitivity=sensitivity, requires_human_confirmation=True,
                executed=False, committed=False,
                message="Recebimento de cliente não configurado neste ambiente.",
            )
        try:
            receipt = self._customer_receipts.receive(command, user=context.requested_by)
        except Exception as error:
            message = str(error) if isinstance(error, ValueError) else "Não foi possível registrar o recebimento."
            return CommercialActionResult(
                action="RECEBER_PAGAMENTO_CLIENTE", context=context,
                sensitivity=sensitivity, requires_human_confirmation=True,
                executed=True, committed=False, message=message,
            )
        event_failed = False
        callback = getattr(self._events, "customer_payment_received", None)
        if callback is not None:
            try:
                callback(CustomerPaymentReceived(
                    receipt=receipt, request_id=context.request_id,
                    requested_by=context.requested_by,
                ))
            except Exception:
                event_failed = True
        message = f"Recebimento #{receipt.movement_id} confirmado."
        if event_failed:
            message += " Um efeito secundário falhou; não registre novamente."
        return CommercialActionResult(
            action="RECEBER_PAGAMENTO_CLIENTE", context=context,
            sensitivity=sensitivity, requires_human_confirmation=True,
            executed=True, committed=True, message=message,
            resource_id=receipt.movement_id, secondary_effect_failed=event_failed,
        )
