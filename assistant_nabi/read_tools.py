from __future__ import annotations

from datetime import date

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

CUSTOMER_CREDIT = ToolDefinition(
    "clientes.consultar_credito",
    ToolKind.READ,
    CapabilityLevel.READ,
    "clientes",
    "view",
    ToolSchema((ParameterDefinition("customer_id", ParameterType.INTEGER, required=True),)),
)

LOW_STOCK = ToolDefinition(
    "estoque.listar_baixo",
    ToolKind.READ,
    CapabilityLevel.READ,
    "produtos",
    "view",
    ToolSchema(),
)

DAILY_SALES = ToolDefinition(
    "vendas.listar_dia",
    ToolKind.READ,
    CapabilityLevel.READ,
    "vendas",
    "view",
    ToolSchema((ParameterDefinition("day", ParameterType.TEXT, required=True, max_length=10),)),
)

DAILY_RECEIPTS = ToolDefinition(
    "recebimentos.listar_dia",
    ToolKind.READ,
    CapabilityLevel.READ,
    "financeiro",
    "view",
    ToolSchema((ParameterDefinition("day", ParameterType.TEXT, required=True, max_length=10),)),
)

OVERDUE_CHARGES = ToolDefinition(
    "cobrancas.listar_vencidas",
    ToolKind.READ,
    CapabilityLevel.READ,
    "financeiro",
    "view",
    ToolSchema(),
)

FINANCIAL_SUMMARY = ToolDefinition(
    "financeiro.resumo",
    ToolKind.READ,
    CapabilityLevel.READ,
    "financeiro",
    "view",
    ToolSchema((
        ParameterDefinition("start_date", ParameterType.TEXT, required=True, max_length=10),
        ParameterDefinition("end_date", ParameterType.TEXT, required=True, max_length=10),
    )),
)

CASH_FLOW = ToolDefinition(
    "financeiro.fluxo_caixa",
    ToolKind.READ,
    CapabilityLevel.READ,
    "financeiro",
    "view",
    FINANCIAL_SUMMARY.schema,
)

FINANCIAL_RECEIVABLES = ToolDefinition(
    "financeiro.listar_receber",
    ToolKind.READ,
    CapabilityLevel.READ,
    "financeiro",
    "view",
    ToolSchema((ParameterDefinition(
        "situation", ParameterType.TEXT, required=True,
        allowed_values=("ABERTOS", "VENCIDOS"),
    ),)),
)

FINANCIAL_PAYABLES = ToolDefinition(
    "financeiro.listar_pagar",
    ToolKind.READ,
    CapabilityLevel.READ,
    "financeiro",
    "view",
    FINANCIAL_RECEIVABLES.schema,
)


def _iso_day(value: str, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} deve usar AAAA-MM-DD.") from exc
    if value != parsed.isoformat():
        raise ValueError(f"{field} deve usar AAAA-MM-DD.")
    return parsed


def _period(parameters) -> tuple[date, date]:
    start = _iso_day(parameters["start_date"], "Data inicial")
    end = _iso_day(parameters["end_date"], "Data final")
    if end < start:
        raise ValueError("A data final não pode ser anterior à inicial.")
    if (end - start).days > 366:
        raise ValueError("O período máximo de consulta é 366 dias.")
    return start, end


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


class CustomerCreditTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        summary = self._queries.customer_credit(request.parameters["customer_id"])
        return {
            "customer_id": summary.customer_id,
            "credit_limit": format(summary.credit_limit, "f"),
            "debt_balance": format(summary.debt_balance, "f"),
            "available_credit": format(summary.available_credit, "f"),
        }


class LowStockTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        records = self._queries.low_stock_products()
        return {"items": [
            {
                "product_id": record.product_id,
                "code": record.code,
                "description": record.description,
                "current_quantity": format(record.current_quantity, "f"),
                "minimum_quantity": format(record.minimum_quantity, "f"),
            }
            for record in records[:50]
        ]}


class DailySalesTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        day = _iso_day(request.parameters["day"], "Data")
        records = self._queries.daily_sales(day)
        return {"day": day.isoformat(), "items": [
            {
                "sale_id": record.sale_id,
                "customer_id": record.customer_id,
                "description": record.description,
                "total": format(record.total, "f"),
                "occurred_at": record.occurred_at,
                "status": record.status,
                "cancelled": record.cancelled,
            }
            for record in records[:50]
        ]}


class DailyReceiptsTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        day = _iso_day(request.parameters["day"], "Data")
        records = self._queries.daily_receipts(day)
        return {"day": day.isoformat(), "items": [
            {
                "payment_id": record.payment_id,
                "amount": format(record.amount, "f"),
                "payment_method": record.payment_method,
                "paid_at": record.paid_at,
                "customer_name": record.customer_name,
            }
            for record in records[:50]
        ]}


class OverdueChargesTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        records = self._queries.overdue_charges()
        return {"items": [
            {
                "installment_id": record.installment_id,
                "customer_id": record.customer_id,
                "customer_name": record.customer_name,
                "installment_number": record.installment_number,
                "open_amount": format(record.open_amount, "f"),
                "due_date": record.due_date.isoformat(),
            }
            for record in records[:50]
        ]}


class FinancialSummaryTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        start, end = _period(request.parameters)
        summary = self._queries.financial_summary(start, end)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "receivable_open": format(summary.receivable_open, "f"),
            "receivable_overdue": format(summary.receivable_overdue, "f"),
            "payable_open": format(summary.payable_open, "f"),
            "payable_due_today": format(summary.payable_due_today, "f"),
            "received_in_period": format(summary.received_in_period, "f"),
            "paid_in_period": format(summary.paid_in_period, "f"),
        }


class CashFlowTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        start, end = _period(request.parameters)
        records = self._queries.cash_flow(start, end)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "items": [
                {
                    "payment_id": record.payment_id,
                    "occurred_at": record.occurred_at.isoformat(),
                    "direction": record.direction,
                    "amount": format(record.amount, "f"),
                    "origin": record.origin,
                }
                for record in records[:100]
            ],
        }


def _minimal_titles(records, *, party_id: str, party_name: str) -> dict:
    ordered = sorted(records, key=lambda item: (item.due_date, item.title_id))[:50]
    return {"items": [{
        "title_id": record.title_id,
        party_id: getattr(record, party_id),
        party_name: getattr(record, party_name),
        "open_amount": format(record.open_amount, ".2f"),
        "due_date": record.due_date.isoformat(),
        "status": record.status,
        "overdue": record.overdue,
    } for record in ordered]}


class FinancialReceivablesTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        situation = request.parameters["situation"]
        records = (
            self._queries.overdue_receivables()
            if situation == "VENCIDOS"
            else self._queries.receivables(open_only=True)
        )
        return _minimal_titles(
            records, party_id="customer_id", party_name="customer_name"
        )


class FinancialPayablesTool:
    def __init__(self, query_service) -> None:
        self._queries = query_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        situation = request.parameters["situation"]
        records = self._queries.payables(
            open_only=True, overdue=situation == "VENCIDOS"
        )
        return _minimal_titles(
            records, party_id="beneficiary_id", party_name="beneficiary_name"
        )


def register_commercial_read_tools(registry, query_service) -> None:
    """Expõe somente DTOs mínimos da fachada comercial de consultas."""

    registry.register(PRODUCT_SEARCH, ProductSearchTool(query_service))
    registry.register(PRODUCT_STOCK, ProductStockTool(query_service))
    registry.register(CUSTOMER_SEARCH, CustomerSearchTool(query_service))
    registry.register(CUSTOMER_CREDIT, CustomerCreditTool(query_service))
    registry.register(LOW_STOCK, LowStockTool(query_service))
    registry.register(DAILY_SALES, DailySalesTool(query_service))
    registry.register(DAILY_RECEIPTS, DailyReceiptsTool(query_service))
    registry.register(OVERDUE_CHARGES, OverdueChargesTool(query_service))


def register_financial_read_tools(registry, query_service) -> None:
    """Expõe totais financeiros mínimos sem títulos, documentos ou contatos."""

    if query_service is None:
        return
    registry.register(FINANCIAL_SUMMARY, FinancialSummaryTool(query_service))
    registry.register(CASH_FLOW, CashFlowTool(query_service))
    registry.register(FINANCIAL_RECEIVABLES, FinancialReceivablesTool(query_service))
    registry.register(FINANCIAL_PAYABLES, FinancialPayablesTool(query_service))
