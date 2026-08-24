from __future__ import annotations

from .contracts import CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition, ToolKind, ToolSchema


PREPARE_PRODUCT_CREATE = ToolDefinition(
    "produtos.preparar_cadastro", ToolKind.DRAFT, CapabilityLevel.DRAFT,
    "produtos", "create", ToolSchema((
        ParameterDefinition("description", ParameterType.TEXT, required=True, max_length=160),
        ParameterDefinition("code", ParameterType.TEXT, max_length=40),
        ParameterDefinition("sale_price", ParameterType.DECIMAL_TEXT, required=True),
        ParameterDefinition("cost_price", ParameterType.DECIMAL_TEXT),
        ParameterDefinition("barcode", ParameterType.TEXT, max_length=40),
        ParameterDefinition("minimum_stock", ParameterType.DECIMAL_TEXT),
        ParameterDefinition("category_id", ParameterType.INTEGER),
    )),
)
PREPARE_STOCK_MOVEMENT = ToolDefinition(
    "estoque.preparar_movimento", ToolKind.DRAFT, CapabilityLevel.DRAFT,
    "produtos", "edit", ToolSchema((
        ParameterDefinition("operation", ParameterType.TEXT, required=True,
                            allowed_values=("STOCK_RECEIVE", "STOCK_REMOVE", "STOCK_ADJUST")),
        ParameterDefinition("product_id", ParameterType.INTEGER, required=True),
        ParameterDefinition("value", ParameterType.DECIMAL_TEXT, required=True),
        ParameterDefinition("reason", ParameterType.TEXT, required=True, max_length=300),
        ParameterDefinition("reference", ParameterType.TEXT, max_length=80),
    )),
)


class PrepareProductCreateTool:
    def __init__(self, service): self._service = service
    def execute(self, request, *, actor):
        draft = self._service.create_product(**request.parameters)
        return {
            "draft_id": draft.draft_id, "fingerprint": draft.fingerprint,
            "operation_kind": draft.operation_kind, "code": draft.code,
            "description": draft.description, "sale_price": format(draft.sale_price, "f"),
            "cost_price": format(draft.cost_price, "f"), "barcode": draft.barcode,
            "minimum_stock": format(draft.minimum_stock, "f"),
            "category_id": draft.category_id, "current_stock": "0.0000",
            "requires_reinforced_confirmation": True, "persisted": False,
        }


class PrepareStockMovementTool:
    def __init__(self, service): self._service = service
    def execute(self, request, *, actor):
        draft = self._service.create_stock(**request.parameters)
        return {
            "draft_id": draft.draft_id, "fingerprint": draft.fingerprint,
            "operation_kind": draft.operation_kind, "product_id": draft.product_id,
            "product_code": draft.product_code, "product_description": draft.product_description,
            "amount": None if draft.amount is None else format(draft.amount, "f"),
            "previous_balance": format(draft.previous_balance, "f"),
            "new_balance": format(draft.new_balance, "f"), "reason": draft.reason,
            "reference": draft.reference, "requires_reinforced_confirmation": True,
            "persisted": False,
        }


def register_product_stock_draft_tools(registry, service):
    registry.register(PREPARE_PRODUCT_CREATE, PrepareProductCreateTool(service))
    registry.register(PREPARE_STOCK_MOVEMENT, PrepareStockMovementTool(service))
