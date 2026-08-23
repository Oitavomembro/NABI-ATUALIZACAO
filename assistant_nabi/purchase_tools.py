from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)
from .purchase_drafts import PurchaseReceiptItemRequest


PREPARE_PURCHASE_RECEIPT = ToolDefinition(
    "compras.preparar_recebimento",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "compras",
    "create",
    ToolSchema((
        ParameterDefinition("order_id", ParameterType.INTEGER, required=True),
        ParameterDefinition("order_item_ids", ParameterType.INTEGER_LIST, required=True),
        ParameterDefinition("quantities", ParameterType.DECIMAL_TEXT_LIST, required=True),
        ParameterDefinition("unit_costs", ParameterType.DECIMAL_TEXT_LIST, required=True),
        ParameterDefinition("document", ParameterType.TEXT, max_length=80),
        ParameterDefinition("generate_payable", ParameterType.BOOLEAN),
        ParameterDefinition("due_date", ParameterType.TEXT, max_length=10),
    )),
)


class PreparePurchaseReceiptTool:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        ids = request.parameters["order_item_ids"]
        quantities = request.parameters["quantities"]
        costs = request.parameters["unit_costs"]
        if len(ids) != len(quantities) or len(ids) != len(costs):
            raise ValueError("Itens, quantidades e custos possuem tamanhos diferentes.")
        draft = self._service.create(
            request.parameters["order_id"],
            tuple(
                PurchaseReceiptItemRequest(item_id, quantity, cost)
                for item_id, quantity, cost in zip(ids, quantities, costs)
            ),
            document=request.parameters.get("document", ""),
            generate_payable=request.parameters.get("generate_payable", False),
            due_date=request.parameters.get("due_date"),
        )
        return {
            "draft_id": draft.draft_id,
            "fingerprint": draft.fingerprint,
            "operation_kind": draft.operation_kind,
            "order_id": draft.order_id,
            "supplier_id": draft.supplier_id,
            "supplier_name": draft.supplier_name,
            "document": draft.document,
            "generate_payable": draft.generate_payable,
            "due_date": draft.due_date,
            "total": format(draft.total, "f"),
            "items": [
                {
                    "order_item_id": item.order_item_id,
                    "product_id": item.product_id,
                    "code": item.code,
                    "description": item.description,
                    "quantity": format(item.quantity, "f"),
                    "pending_before": format(item.pending_before, "f"),
                    "pending_after": format(item.pending_after, "f"),
                    "unit_cost": format(item.unit_cost, "f"),
                    "line_total": format(item.line_total, "f"),
                }
                for item in draft.items
            ],
            "requires_reinforced_confirmation": True,
            "execution_blocked": True,
            "persisted": False,
        }


def register_purchase_draft_tools(registry, service) -> None:
    registry.register(PREPARE_PURCHASE_RECEIPT, PreparePurchaseReceiptTool(service))
