from __future__ import annotations

from .adapters import AdminAssistantAuditAdapter, CurrentSessionPermissionAdapter
from .application import AssistantApplicationService
from .read_tools import register_commercial_read_tools, register_financial_read_tools
from .registry import ReadOnlyToolRegistry
from .registry import DraftToolRegistry
from .draft_tools import register_sale_draft_tools
from .sale_drafts import SaleDraftService
from .confirmations import DraftConfirmationService
from .draft_catalog import AssistantDraftCatalog
from .purchase_tools import register_purchase_draft_tools
from .nfe_entry_tools import register_nfe_entry_draft_tools


def create_read_only_assistant(
    *,
    model,
    query_service,
    security_service,
    audit_service,
    session_id: str,
    event_bus=None,
    financial_query_service=None,
) -> AssistantApplicationService:
    """Compõe a Nabi de consulta usando apenas sessão, auditoria e fachada oficiais."""

    if query_service is None:
        raise ValueError("O serviço comercial de consultas é obrigatório para a Nabi.")
    if model is None:
        raise ValueError("O provedor local homologado é obrigatório para a Nabi.")
    if security_service is None:
        raise ValueError("O serviço de segurança é obrigatório para a Nabi.")
    if audit_service is None:
        raise ValueError("O serviço de auditoria é obrigatório para a Nabi.")

    permissions = CurrentSessionPermissionAdapter(
        security_service, session_id=session_id
    )
    audit = AdminAssistantAuditAdapter(audit_service, event_bus=event_bus)
    registry = ReadOnlyToolRegistry(permissions=permissions, audit=audit)
    register_commercial_read_tools(registry, query_service)
    register_financial_read_tools(registry, financial_query_service)
    return AssistantApplicationService(
        model=model,
        registry=registry,
        permissions=permissions,
    )


def create_draft_assistant(
    *, model, query_service, security_service, audit_service, session_id: str,
    event_bus=None, purchase_draft_service=None, purchase_executor=None,
    nfe_entry_draft_service=None, nfe_entry_executor=None,
    financial_query_service=None,
) -> AssistantApplicationService:
    """Compõe consultas e rascunhos; não registra ferramentas mutáveis."""
    for value, message in (
        (model, "O provedor local homologado é obrigatório para a Nabi."),
        (query_service, "O serviço comercial de consultas é obrigatório para a Nabi."),
        (security_service, "O serviço de segurança é obrigatório para a Nabi."),
        (audit_service, "O serviço de auditoria é obrigatório para a Nabi."),
    ):
        if value is None:
            raise ValueError(message)
    permissions = CurrentSessionPermissionAdapter(
        security_service, session_id=session_id
    )
    audit = AdminAssistantAuditAdapter(
        audit_service, event_bus=event_bus
    )
    registry = DraftToolRegistry(permissions=permissions, audit=audit)
    register_commercial_read_tools(registry, query_service)
    register_financial_read_tools(registry, financial_query_service)
    drafts = SaleDraftService(query_service)
    draft_catalog = AssistantDraftCatalog(
        drafts, purchase_draft_service, nfe_entry_draft_service
    )
    confirmations = DraftConfirmationService()
    register_sale_draft_tools(registry, drafts)
    if purchase_draft_service is not None:
        register_purchase_draft_tools(registry, purchase_draft_service)
    if nfe_entry_draft_service is not None:
        register_nfe_entry_draft_tools(registry, nfe_entry_draft_service)
    return AssistantApplicationService(
        model=model, registry=registry, permissions=permissions,
        draft_service=draft_catalog, confirmation_service=confirmations,
        purchase_executor=purchase_executor,
        nfe_entry_executor=nfe_entry_executor,
    )
