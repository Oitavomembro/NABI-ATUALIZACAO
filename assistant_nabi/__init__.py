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
from .ui_tools import OPEN_MODULE_HUB, OPEN_PRODUCT_SEARCH, register_ui_intent_tools
from .application import AssistantApplicationService, UnavailableAssistantService
from .unavailable_provider import (
    AssistantProviderUnavailableError,
    UnavailableLanguageModelAdapter,
)
from .local_provider import LocalOpenAICompatibleModelAdapter
from .composition import (
    create_local_read_only_assistant_service,
    create_unavailable_read_only_assistant_service,
)
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
from .customer_drafts import CustomerRegistrationDraft, CustomerRegistrationDraftService
from .customer_gateway import NabiCodeCustomerRegistrationGateway
from .customer_tools import PREPARE_CUSTOMER_REGISTRATION
from .customer_receipt_drafts import CustomerReceiptDraft, CustomerReceiptDraftService
from .customer_receipt_gateway import NabiCodeCustomerReceiptAssistantGateway
from .customer_receipt_tools import PREPARE_CUSTOMER_RECEIPT
from .report_tools import REPORT_INDICATORS, register_report_read_tools
from .cash_tools import CASH_CURRENT, register_cash_read_tools
from .purchase_read_tools import (
    GET_PURCHASE_ORDER, LIST_PURCHASE_ORDERS, LIST_SUPPLIERS,
    register_purchase_read_tools,
)
from .procurement_drafts import (
    PurchaseOrderDraft, PurchaseOrderDraftItem, PurchaseOrderDraftService,
    PurchaseOrderItemRequest, SupplierRegistrationDraft,
    SupplierRegistrationDraftService,
)
from .procurement_gateway import NabiCodeProcurementAssistantGateway
from .procurement_tools import PREPARE_PURCHASE_ORDER, PREPARE_SUPPLIER
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
    "CustomerRegistrationDraft",
    "CustomerRegistrationDraftService",
    "NabiCodeCustomerRegistrationGateway",
    "PREPARE_CUSTOMER_REGISTRATION",
    "CustomerReceiptDraft",
    "CustomerReceiptDraftService",
    "NabiCodeCustomerReceiptAssistantGateway",
    "PREPARE_CUSTOMER_RECEIPT",
    "REPORT_INDICATORS",
    "CASH_CURRENT",
    "DraftConfirmationService",
    "AssistantApplicationService",
    "AssistantTurn",
    "UnavailableAssistantService",
    "AssistantProviderUnavailableError",
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
    "register_report_read_tools",
    "register_cash_read_tools",
    "LIST_SUPPLIERS",
    "LIST_PURCHASE_ORDERS",
    "GET_PURCHASE_ORDER",
    "register_purchase_read_tools",
    "PurchaseOrderDraft",
    "PurchaseOrderDraftItem",
    "PurchaseOrderDraftService",
    "PurchaseOrderItemRequest",
    "SupplierRegistrationDraft",
    "SupplierRegistrationDraftService",
    "NabiCodeProcurementAssistantGateway",
    "PREPARE_PURCHASE_ORDER",
    "PREPARE_SUPPLIER",
    "OPEN_PRODUCT_SEARCH",
    "OPEN_MODULE_HUB",
    "register_ui_intent_tools",
    "create_read_only_assistant",
    "create_draft_assistant",
    "verify_model_artifact",
    "verify_runtime_directory",
    "UnavailableLanguageModelAdapter",
    "create_local_read_only_assistant_service",
    "create_unavailable_read_only_assistant_service",
]
