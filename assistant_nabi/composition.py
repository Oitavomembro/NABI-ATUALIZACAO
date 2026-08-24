from __future__ import annotations

from .adapters import AdminAssistantAuditAdapter, CurrentSessionPermissionAdapter
from .application import AssistantApplicationService
from .local_provider import LocalOpenAICompatibleModelAdapter
from .read_tools import register_commercial_read_tools
from .registry import ReadOnlyToolRegistry
from .unavailable_provider import UnavailableLanguageModelAdapter


def _required_dependency(value, name: str):
    if value is None:
        raise ValueError(f"A dependência real {name} é obrigatória para compor a Nabi.")
    return value


def _compose_read_only_service(
    *,
    security_service,
    audit_service,
    commercial_query_service,
    session_id: str,
    model,
    event_bus=None,
) -> AssistantApplicationService:
    security = _required_dependency(security_service, "security_service")
    audit = _required_dependency(audit_service, "audit_service")
    queries = _required_dependency(commercial_query_service, "commercial_query_service")
    provider = _required_dependency(model, "model")

    permissions = CurrentSessionPermissionAdapter(security, session_id=session_id)
    audit_port = AdminAssistantAuditAdapter(audit, event_bus=event_bus)
    registry = ReadOnlyToolRegistry(permissions=permissions, audit=audit_port)
    register_commercial_read_tools(registry, queries)
    return AssistantApplicationService(
        model=provider,
        registry=registry,
        permissions=permissions,
    )


def create_local_read_only_assistant_service(
    *,
    security_service,
    audit_service,
    commercial_query_service,
    session_id: str,
    endpoint: str,
    model_name: str,
    event_bus=None,
    transport=None,
    timeout_seconds: float = 30.0,
) -> AssistantApplicationService:
    """Compõe a Nabi local somente leitura; o chamador fornece toda autoridade real."""

    model = LocalOpenAICompatibleModelAdapter(
        endpoint=endpoint,
        model=model_name,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    return _compose_read_only_service(
        security_service=security_service,
        audit_service=audit_service,
        commercial_query_service=commercial_query_service,
        session_id=session_id,
        model=model,
        event_bus=event_bus,
    )


def create_unavailable_read_only_assistant_service(
    *,
    security_service,
    audit_service,
    commercial_query_service,
    session_id: str,
    event_bus=None,
) -> AssistantApplicationService:
    """Compõe o mesmo limite seguro sem configurar ou contatar um modelo."""

    return _compose_read_only_service(
        security_service=security_service,
        audit_service=audit_service,
        commercial_query_service=commercial_query_service,
        session_id=session_id,
        model=UnavailableLanguageModelAdapter(),
        event_bus=event_bus,
    )
