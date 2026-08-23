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
from .application import AssistantApplicationService, UnavailableAssistantService
from .local_provider import LocalOpenAICompatibleModelAdapter
from .bootstrap import create_read_only_assistant

__all__ = [
    "AssistantActor",
    "AssistantApplicationService",
    "AssistantTurn",
    "UnavailableAssistantService",
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
    "create_read_only_assistant",
]
