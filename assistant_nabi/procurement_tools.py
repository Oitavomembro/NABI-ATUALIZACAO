from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)
from .procurement_drafts import PurchaseOrderItemRequest


PREPARE_SUPPLIER = ToolDefinition(
    "compras.preparar_fornecedor", ToolKind.DRAFT, CapabilityLevel.DRAFT,
    "compras", "create", ToolSchema((
        ParameterDefinition("name", ParameterType.TEXT, required=True, max_length=160),
        ParameterDefinition("legal_name", ParameterType.TEXT, max_length=200),
        ParameterDefinition("document", ParameterType.TEXT, max_length=20),
        ParameterDefinition("phone", ParameterType.TEXT, max_length=30),
        ParameterDefinition("email", ParameterType.TEXT, max_length=160),
    )),
)
PREPARE_PURCHASE_ORDER = ToolDefinition(
    "compras.preparar_pedido", ToolKind.DRAFT, CapabilityLevel.DRAFT,
    "compras", "create", ToolSchema((
        ParameterDefinition("supplier_id", ParameterType.INTEGER, required=True),
        ParameterDefinition("product_ids", ParameterType.INTEGER_LIST, required=True),
        ParameterDefinition("quantities", ParameterType.DECIMAL_TEXT_LIST, required=True),
        ParameterDefinition("unit_costs", ParameterType.DECIMAL_TEXT_LIST, required=True),
        ParameterDefinition("notes", ParameterType.TEXT, max_length=500),
    )),
)


class PrepareSupplierTool:
    def __init__(self, service): self._service = service
    def execute(self, request: ToolRequest, *, actor):
        draft = self._service.create(**request.parameters)
        return {
            "draft_id": draft.draft_id, "fingerprint": draft.fingerprint,
            "operation_kind": draft.operation_kind, "name": draft.name,
            "legal_name": draft.legal_name, "document": draft.document,
            "phone": draft.phone, "email": draft.email,
            "requires_reinforced_confirmation": True, "persisted": False,
        }


class PreparePurchaseOrderTool:
    def __init__(self, service): self._service = service
    def execute(self, request: ToolRequest, *, actor):
        product_ids = request.parameters["product_ids"]
        quantities = request.parameters["quantities"]
        costs = request.parameters["unit_costs"]
        if len(product_ids) != len(quantities) or len(product_ids) != len(costs):
            raise ValueError("Produtos, quantidades e custos possuem tamanhos diferentes.")
        draft = self._service.create(
            request.parameters["supplier_id"],
            tuple(PurchaseOrderItemRequest(*values) for values in zip(product_ids, quantities, costs)),
            notes=request.parameters.get("notes", ""),
        )
        return {
            "draft_id": draft.draft_id, "fingerprint": draft.fingerprint,
            "operation_kind": draft.operation_kind,
            "supplier_id": draft.supplier_id, "supplier_name": draft.supplier_name,
            "notes": draft.notes, "total": format(draft.total, "f"),
            "items": [{
                "product_id": item.product_id, "code": item.code,
                "description": item.description, "quantity": format(item.quantity, "f"),
                "unit_cost": format(item.unit_cost, "f"),
                "line_total": format(item.line_total, "f"),
            } for item in draft.items],
            "requires_reinforced_confirmation": True, "persisted": False,
        }


def register_procurement_draft_tools(registry, supplier_service=None, order_service=None):
    if supplier_service is not None:
        registry.register(PREPARE_SUPPLIER, PrepareSupplierTool(supplier_service))
    if order_service is not None:
        registry.register(PREPARE_PURCHASE_ORDER, PreparePurchaseOrderTool(order_service))
