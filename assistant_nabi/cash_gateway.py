from __future__ import annotations

from .confirmations import ConfirmedDraftAuthorization


class NabiCodeCashAssistantGateway:
    def __init__(self, application_service) -> None:
        self._application = application_service

    def execute(self, draft, authorization):
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("A operação de caixa exige autorização do broker.")
        operation = str(draft.operation_kind)
        if not operation.startswith("CASH_"):
            raise TypeError("O rascunho não representa uma operação de caixa.")
        current = self._application.current()
        current_id = current.session.id if current.session is not None else None
        if draft.expected_session_id is not None and current_id != draft.expected_session_id:
            raise ValueError("A sessão de caixa mudou; prepare e revise um novo rascunho.")
        grant = authorization.consume(draft, operation=operation)
        key = f"nabi:cash:{draft.draft_id}"
        if operation == "CASH_OPEN":
            return self._application.open_assisted(
                draft.amount, draft.opening_mode, username=grant.username,
                idempotency_key=key, operation_fingerprint=draft.fingerprint,
            )
        if operation in {"CASH_SANGRIA", "CASH_SUPRIMENTO"}:
            return self._application.movement_assisted(
                operation.removeprefix("CASH_"), draft.amount, draft.note,
                username=grant.username, idempotency_key=key,
                operation_fingerprint=draft.fingerprint,
            )
        return self._application.close_assisted(
            draft.amount, draft.note, username=grant.username,
            idempotency_key=key, operation_fingerprint=draft.fingerprint,
        )
