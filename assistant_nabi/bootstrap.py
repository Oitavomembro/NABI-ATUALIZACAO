from __future__ import annotations

from .adapters import AdminAssistantAuditAdapter, CurrentSessionPermissionAdapter
from .application import AssistantApplicationService
from .read_tools import register_commercial_read_tools
from .registry import ReadOnlyToolRegistry


def create_read_only_assistant(
    *,
    model,
    query_service,
    security_service,
    audit_service,
    session_id: str,
    event_bus=None,
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
    return AssistantApplicationService(
        model=model,
        registry=registry,
        permissions=permissions,
    )
