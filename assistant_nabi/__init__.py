"""Fundação segura e independente de provedor para a assistente Nabi."""

from .contracts import (
    AssistantActor,
    AssistantTurn,
    CapabilityLevel,
    ParameterDefinition,
    ParameterType,
    ModelReply,
    ToolDefinition,
    ToolKind,
    ToolRequest,
    ToolResult,
    ToolSchema,
)
from .registry import ReadOnlyToolRegistry
from .adapters import AdminAssistantAuditAdapter, CurrentSessionPermissionAdapter
from .read_tools import register_commercial_read_tools
from .application import AssistantApplicationService
from .unavailable_provider import (
    AssistantProviderUnavailableError,
    UnavailableLanguageModelAdapter,
)
from .local_provider import LocalOpenAICompatibleModelAdapter

__all__ = [
    "AssistantActor",
    "AssistantApplicationService",
    "AssistantTurn",
    "AssistantProviderUnavailableError",
    "AdminAssistantAuditAdapter",
    "CapabilityLevel",
    "ParameterDefinition",
    "ParameterType",
    "ModelReply",
    "LocalOpenAICompatibleModelAdapter",
    "ReadOnlyToolRegistry",
    "CurrentSessionPermissionAdapter",
    "ToolDefinition",
    "ToolKind",
    "ToolRequest",
    "ToolResult",
    "ToolSchema",
    "register_commercial_read_tools",
    "UnavailableLanguageModelAdapter",
]
