from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)
from .sale_drafts import SaleDraftItemRequest


CREATE_SALE_DRAFT = ToolDefinition(
    "vendas.criar_rascunho",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "vendas",
    "create",
    ToolSchema((
        ParameterDefinition("product_ids", ParameterType.INTEGER_LIST, required=True),
        ParameterDefinition("quantities", ParameterType.DECIMAL_TEXT_LIST, required=True),
        ParameterDefinition(
            "payment_method", ParameterType.TEXT, required=True,
            allowed_values=("DINHEIRO", "PIX", "DEBITO", "CREDITO", "CREDIARIO", "OUTROS"),
        ),
        ParameterDefinition("customer_id", ParameterType.INTEGER),
    )),
)


class CreateSaleDraftTool:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        product_ids = request.parameters["product_ids"]
        quantities = request.parameters["quantities"]
        if len(product_ids) != len(quantities):
            raise ValueError("Produtos e quantidades possuem tamanhos diferentes.")
        draft = self._service.create(
            tuple(
                SaleDraftItemRequest(product_id, quantity)
                for product_id, quantity in zip(product_ids, quantities)
            ),
            payment_method=request.parameters["payment_method"],
            customer_id=request.parameters.get("customer_id"),
        )
        return {
            "draft_id": draft.draft_id,
            "fingerprint": draft.fingerprint,
            "customer_id": draft.customer_id,
            "payment_method": draft.payment_method,
            "total": format(draft.total, "f"),
            "items": [
                {
                    "product_id": item.product_id,
                    "code": item.code,
                    "description": item.description,
                    "quantity": format(item.quantity, "f"),
                    "unit_price": format(item.unit_price, "f"),
                    "line_total": format(item.line_total, "f"),
                    "stock_before": format(item.stock_before, "f"),
                    "stock_after": format(item.stock_after, "f"),
                }
                for item in draft.items
            ],
            "requires_confirmation": True,
            "persisted": False,
        }


def register_sale_draft_tools(registry, service) -> None:
    registry.register(CREATE_SALE_DRAFT, CreateSaleDraftTool(service))
