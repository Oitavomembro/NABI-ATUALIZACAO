from __future__ import annotations

from .confirmations import ConfirmedDraftAuthorization
from .safe_error_recovery import FiscalRecoveryDraft, ProductNcmCorrectionDraft


class NabiCodeSafeErrorRecoveryGateway:
    """Consome confirmação humana e delega apenas a portas oficiais estreitas."""

    def __init__(self, product_correction_port, fiscal_outbox_port) -> None:
        if product_correction_port is None or fiscal_outbox_port is None:
            raise ValueError("As portas oficiais de correção e outbox são obrigatórias.")
        self._products = product_correction_port
        self._fiscal = fiscal_outbox_port

    def execute(self, draft, authorization):
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("A operação exige autorização emitida pelo broker.")
        if isinstance(draft, ProductNcmCorrectionDraft):
            grant = authorization.consume(draft, operation=draft.operation_kind)
            return self._products.correct_ncm(
                draft, username=grant.username,
                idempotency_key=f"nabi:product-ncm:{draft.draft_id}",
                operation_fingerprint=draft.fingerprint,
            )
        if not isinstance(draft, FiscalRecoveryDraft):
            raise TypeError("O rascunho não representa uma recuperação segura.")
        grant = authorization.consume(draft, operation=draft.operation_kind)
        actor = self._fiscal.require_authenticated_actor(
            "transmit", operation="consultar e reconciliar a fila fiscal"
        )
        if str(actor or "").strip() != grant.username:
            raise PermissionError("A confirmação fiscal pertence a outro usuário.")
        if draft.operation_kind == "FISCAL_RECONCILE_UNKNOWN":
            record = self._fiscal.reconcile_unknown(draft.queue_id)
        elif draft.operation_kind == "FISCAL_CHECK_RECEIPT":
            record = self._fiscal.force_receipt_check(draft.queue_id)
        else:
            raise TypeError("Ação fiscal segura não reconhecida.")
        return {
            "queue_id": str(record.get("id") or draft.queue_id),
            "status": str(record.get("status") or ""),
            "operation": str(record.get("operation") or ""),
            "safe_action": draft.safe_action,
            "commercial_sale_preserved": True,
            "authorization_claimed": False,
            "blind_resend_performed": False,
        }
