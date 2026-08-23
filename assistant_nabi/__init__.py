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
from .registry import DraftToolRegistry, ReadOnlyToolRegistry
from .adapters import AdminAssistantAuditAdapter, CurrentSessionPermissionAdapter
from .read_tools import register_commercial_read_tools
from .ui_tools import OPEN_PRODUCT_SEARCH, register_ui_intent_tools
from .application import AssistantApplicationService, UnavailableAssistantService
from .local_provider import LocalOpenAICompatibleModelAdapter
from .bootstrap import create_draft_assistant, create_read_only_assistant
from .activation import AuthenticatedAssistantActivation
from .sale_drafts import SaleDraft, SaleDraftItem, SaleDraftItemRequest, SaleDraftService
from .purchase_drafts import (
    PurchaseReceiptDraft, PurchaseReceiptDraftItem, PurchaseReceiptDraftService,
    PurchaseReceiptItemRequest,
)
from .purchase_gateway import NabiCodePurchaseAssistantGateway
from .draft_catalog import AssistantDraftCatalog
from .purchase_composition import create_purchase_assistant_components
from .nfe_entry_drafts import (
    NFeEntryCandidate, NFeEntryDraft, NFeEntryDraftItem, NFeEntryDraftService,
    NFeEntryImportDraft, NFeEntryImportDraftItem,
)
from .nfe_entry_gateway import NabiCodeNFeEntryAssistantGateway
from .confirmations import (
    ConfirmationChallenge, ConfirmedDraftAuthorization, DraftConfirmationService,
)
from .model_artifact import ModelArtifactManifest, verify_model_artifact
from .model_catalog import QWEN3_1_7B_Q4_K_M_CANDIDATE
from .local_runtime import LocalLlamaServer
from .runtime_artifact import (
    LLAMA_CPP_B10537_CPU_X64,
    RuntimeDirectoryManifest,
    verify_runtime_directory,
)

__all__ = [
    "AssistantActor",
    "AuthenticatedAssistantActivation",
    "SaleDraft",
    "SaleDraftItem",
    "SaleDraftItemRequest",
    "SaleDraftService",
    "PurchaseReceiptDraft",
    "PurchaseReceiptDraftItem",
    "PurchaseReceiptDraftService",
    "PurchaseReceiptItemRequest",
    "NabiCodePurchaseAssistantGateway",
    "AssistantDraftCatalog",
    "create_purchase_assistant_components",
    "NFeEntryCandidate",
    "NFeEntryDraft",
    "NFeEntryDraftItem",
    "NFeEntryDraftService",
    "NFeEntryImportDraft",
    "NFeEntryImportDraftItem",
    "NabiCodeNFeEntryAssistantGateway",
    "ConfirmationChallenge",
    "ConfirmedDraftAuthorization",
    "DraftConfirmationService",
    "AssistantApplicationService",
    "AssistantTurn",
    "UnavailableAssistantService",
    "AdminAssistantAuditAdapter",
    "CapabilityLevel",
    "ParameterDefinition",
    "ParameterType",
    "ModelReply",
    "LocalOpenAICompatibleModelAdapter",
    "LocalLlamaServer",
    "LLAMA_CPP_B10537_CPU_X64",
    "ModelArtifactManifest",
    "ReadOnlyToolRegistry",
    "DraftToolRegistry",
    "RuntimeDirectoryManifest",
    "QWEN3_1_7B_Q4_K_M_CANDIDATE",
    "CurrentSessionPermissionAdapter",
    "ToolDefinition",
    "ToolKind",
    "ToolRequest",
    "ToolResult",
    "ToolSchema",
    "register_commercial_read_tools",
    "OPEN_PRODUCT_SEARCH",
    "register_ui_intent_tools",
    "create_read_only_assistant",
    "create_draft_assistant",
    "verify_model_artifact",
    "verify_runtime_directory",
]
