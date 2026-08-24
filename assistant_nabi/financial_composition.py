from __future__ import annotations

from .financial_drafts import FinancialDraftService
from .financial_gateway import NabiCodeFinancialAssistantGateway


def create_financial_assistant_components(commercial_container, financeiro_service):
    actions = getattr(commercial_container, "financial_actions", None)
    if actions is None or financeiro_service is None:
        raise RuntimeError("Serviços financeiros oficiais não estão configurados.")
    gateway = NabiCodeFinancialAssistantGateway(actions, financeiro_service)
    return FinancialDraftService(gateway), gateway
