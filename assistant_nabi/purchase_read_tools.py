from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)


LIST_SUPPLIERS = ToolDefinition(
    "compras.listar_fornecedores", ToolKind.READ, CapabilityLevel.READ,
    "compras", "view", ToolSchema(),
)
LIST_PURCHASE_ORDERS = ToolDefinition(
    "compras.listar_pedidos", ToolKind.READ, CapabilityLevel.READ,
    "compras", "view", ToolSchema((ParameterDefinition(
        "status", ParameterType.TEXT, required=True,
        allowed_values=("TODOS", "ABERTO", "PARCIAL", "RECEBIDO"),
    ),)),
)
GET_PURCHASE_ORDER = ToolDefinition(
    "compras.consultar_pedido", ToolKind.READ, CapabilityLevel.READ,
    "compras", "view", ToolSchema((ParameterDefinition(
        "order_id", ParameterType.INTEGER, required=True,
    ),)),
)


class ListSuppliersTool:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        records = self._service.list_suppliers()
        return {"items": [{
            "supplier_id": item.supplier_id,
            "name": item.name,
            "active": item.active,
        } for item in records[:100]]}


class ListPurchaseOrdersTool:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        records = self._service.list_orders(request.parameters["status"], limit=50)
        return {"items": [{
            "order_id": item.order_id,
            "status": item.status,
            "supplier_name": item.supplier_name,
            "created_at": item.created_at,
            "total": format(item.total, "f"),
            "pending_quantity": format(item.pending_quantity, "f"),
        } for item in records]}


class GetPurchaseOrderTool:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        order = self._service.get_order(request.parameters["order_id"])
        return {
            "order_id": int(order["id"]),
            "status": str(order.get("status") or ""),
            "supplier_name": str(order.get("fornecedor_nome") or ""),
            "items": [{
                "order_item_id": int(item["id"]),
                "product_id": int(item["produto_id"]),
                "code": str(item.get("codigo") or ""),
                "description": str(item.get("nome") or ""),
                "ordered_quantity": format(item["quantidade_pedida"], "f"),
                "received_quantity": format(item["quantidade_recebida"], "f"),
                "pending_quantity": format(item["quantidade_pendente"], "f"),
                "unit_cost": format(item["custo_unitario"], "f"),
            } for item in tuple(order.get("itens") or ())[:100]],
        }


def register_purchase_read_tools(registry, service) -> None:
    if service is None:
        return
    registry.register(LIST_SUPPLIERS, ListSuppliersTool(service))
    registry.register(LIST_PURCHASE_ORDERS, ListPurchaseOrdersTool(service))
    registry.register(GET_PURCHASE_ORDER, GetPurchaseOrderTool(service))
