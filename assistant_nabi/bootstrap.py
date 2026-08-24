from __future__ import annotations

from .adapters import (
    AdminAssistantAuditAdapter, AdminAssistantConfirmationAuditAdapter,
    CurrentSessionPermissionAdapter,
)
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
from .ui_tools import register_ui_intent_tools
from .customer_tools import register_customer_draft_tools
from .customer_receipt_tools import register_customer_receipt_tools
from .report_tools import register_report_read_tools
from .cash_tools import register_cash_read_tools
from .purchase_read_tools import register_purchase_read_tools
from .procurement_tools import register_procurement_draft_tools
from .product_stock_tools import register_product_stock_draft_tools
from .financial_tools import register_financial_draft_tools


def create_read_only_assistant(
    *,
    model,
    query_service,
    security_service,
    audit_service,
    session_id: str,
    event_bus=None,
    financial_query_service=None,
    report_service=None,
    cash_service_factory=None,
    purchase_query_service=None,
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
    register_report_read_tools(registry, report_service)
    register_cash_read_tools(registry, cash_service_factory)
    register_purchase_read_tools(registry, purchase_query_service)
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
    report_service=None,
    cash_service_factory=None,
    customer_draft_service=None, customer_executor=None,
    customer_receipt_draft_service=None, customer_receipt_executor=None,
    purchase_query_service=None,
    supplier_draft_service=None, purchase_order_draft_service=None,
    procurement_executor=None,
    product_stock_draft_service=None, product_stock_executor=None,
    financial_draft_service=None, financial_executor=None,
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
    register_report_read_tools(registry, report_service)
    register_cash_read_tools(registry, cash_service_factory)
    register_purchase_read_tools(registry, purchase_query_service)
    register_ui_intent_tools(registry)
    drafts = SaleDraftService(query_service)
    draft_catalog = AssistantDraftCatalog(
        drafts, purchase_draft_service, nfe_entry_draft_service,
        customer_draft_service,
        customer_receipt_draft_service,
        supplier_draft_service, purchase_order_draft_service,
        product_stock_draft_service,
        financial_draft_service,
    )
    confirmations = DraftConfirmationService(
        audit=AdminAssistantConfirmationAuditAdapter(audit_service)
    )
    register_sale_draft_tools(registry, drafts)
    if purchase_draft_service is not None:
        register_purchase_draft_tools(registry, purchase_draft_service)
    if nfe_entry_draft_service is not None:
        register_nfe_entry_draft_tools(registry, nfe_entry_draft_service)
    if customer_draft_service is not None:
        register_customer_draft_tools(registry, customer_draft_service)
    if customer_receipt_draft_service is not None:
        register_customer_receipt_tools(registry, customer_receipt_draft_service)
    register_procurement_draft_tools(
        registry, supplier_draft_service, purchase_order_draft_service
    )
    if product_stock_draft_service is not None:
        register_product_stock_draft_tools(registry, product_stock_draft_service)
    if financial_draft_service is not None:
        register_financial_draft_tools(registry, financial_draft_service)
    return AssistantApplicationService(
        model=model, registry=registry, permissions=permissions,
        draft_service=draft_catalog, confirmation_service=confirmations,
        purchase_executor=purchase_executor,
        nfe_entry_executor=nfe_entry_executor,
        customer_executor=customer_executor,
        customer_receipt_executor=customer_receipt_executor,
        procurement_executor=procurement_executor,
        product_stock_executor=product_stock_executor,
        financial_executor=financial_executor,
    )
