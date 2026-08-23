from __future__ import annotations

from .contracts import (
    CapabilityLevel,
    ParameterDefinition,
    ParameterType,
    ToolDefinition,
    ToolKind,
    ToolRequest,
    ToolSchema,
)


PRODUCT_SEARCH = ToolDefinition(
    "produtos.pesquisar",
    ToolKind.READ,
    CapabilityLevel.READ,
    "produtos",
    "view",
    ToolSchema((ParameterDefinition("term", ParameterType.TEXT, required=True, max_length=100),)),
)

PRODUCT_STOCK = ToolDefinition(
    "produtos.consultar_estoque",
    ToolKind.READ,
    CapabilityLevel.READ,
    "produtos",
    "view",
    ToolSchema((ParameterDefinition("product_id", ParameterType.INTEGER, required=True),)),
)

CUSTOMER_SEARCH = ToolDefinition(
    "clientes.pesquisar",
    ToolKind.READ,
    CapabilityLevel.READ,
    "clientes",
    "view",
    ToolSchema((ParameterDefinition("term", ParameterType.TEXT, required=True, max_length=100),)),
)


class ProductSearchTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        records = self._queries.search_products(request.parameters["term"], limit=20)
        return {
            "items": [
                {
                    "product_id": record.product_id,
                    "code": record.code,
                    "description": record.description,
                    "sale_price": format(record.unit_price, "f"),
                    "active": record.active,
                }
                for record in records
            ]
        }


class ProductStockTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        stock = self._queries.product_stock(request.parameters["product_id"])
        return {
            "product_id": stock.product_id,
            "current_quantity": format(stock.current_quantity, "f"),
            "minimum_quantity": format(stock.minimum_quantity, "f"),
            "available": stock.available,
            "status": stock.status,
            "allow_negative_stock": stock.allow_negative_stock,
        }


class CustomerSearchTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        records = self._queries.search_customers(request.parameters["term"], limit=20)
        return {
            "items": [
                {
                    "customer_id": record.customer_id,
                    "code": record.code,
                    "record_number": record.record_number,
                    "name": record.name,
                }
                for record in records
            ]
        }


def register_commercial_read_tools(registry, query_service) -> None:
    """Expõe somente DTOs mínimos da fachada comercial de consultas."""

    registry.register(PRODUCT_SEARCH, ProductSearchTool(query_service))
    registry.register(PRODUCT_STOCK, ProductStockTool(query_service))
    registry.register(CUSTOMER_SEARCH, CustomerSearchTool(query_service))
