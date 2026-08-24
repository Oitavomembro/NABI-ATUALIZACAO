from __future__ import annotations

from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.financial_dto import (
    CreateFinancialTitleCommand, SettleFinancialTitleCommand,
)
from commercial.domain.money import MoneyCodec

from .confirmations import ConfirmedDraftAuthorization


class NabiCodeFinancialAssistantGateway:
    """Prepara estado e executa somente ação financeira confirmada."""

    def __init__(self, action_service, financeiro_service) -> None:
        if action_service is None or financeiro_service is None:
            raise ValueError("Serviços financeiros oficiais são obrigatórios.")
        self._actions = action_service
        self._service = financeiro_service

    @property
    def payment_methods(self):
        return frozenset(self._service.FORMAS_PAGAMENTO)

    def get_title(self, title_id: int):
        try:
            return self._service.obter_titulo(int(title_id))
        except ValueError:
            return None

    def execute(self, draft, authorization):
        operation = str(getattr(draft, "operation_kind", ""))
        if not operation.startswith("FINANCIAL_"):
            raise TypeError("O rascunho não representa operação financeira.")
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("A operação financeira exige autorização do broker.")
        if operation.startswith("FINANCIAL_SETTLE_"):
            current = self.get_title(draft.title_id)
            if current is None or str(current.get("tipo") or "").upper() != draft.title_type:
                raise ValueError("O título financeiro mudou ou não existe mais.")
            open_amount = MoneyCodec.parse(current["saldo_aberto"], field="saldo aberto")
            if open_amount != draft.previous_open_amount:
                raise ValueError("O saldo do título mudou; prepare e revise uma nova baixa.")
        grant = authorization.consume(draft, operation=operation)
        context = ActionContext(grant.username, ActionOrigin.AI, request_id=draft.draft_id)
        if operation.startswith("FINANCIAL_CREATE_"):
            command = CreateFinancialTitleCommand(
                amount=draft.amount, due_date=draft.due_date, party_id=draft.party_id,
                party_name=draft.party_name, document=draft.document,
                description=draft.description, notes=draft.notes, issue_date=draft.issue_date,
            )
            method = (self._actions.create_receivable if draft.title_type == "RECEBER"
                      else self._actions.create_payable)
        else:
            command = SettleFinancialTitleCommand(
                title_id=draft.title_id, amount=draft.amount,
                payment_method=draft.payment_method, payment_date=draft.payment_date,
                notes=draft.notes,
            )
            method = (self._actions.settle_receivable if draft.title_type == "RECEBER"
                      else self._actions.settle_payable)
        result = method(command, context=context, confirmed=True,
                        operation_fingerprint=draft.fingerprint)
        if not result.committed:
            raise ValueError(result.message)
        return result
