from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from assistant_nabi import AssistantActor, DraftToolRegistry, ReadOnlyToolRegistry, ToolRequest
from assistant_nabi.read_tools import (
    register_commercial_read_tools,
    register_financial_read_tools,
)
from assistant_nabi.ui_tools import register_ui_intent_tools
from commercial.application.financial_dto import (
    CashFlowEntry, FinancialSummary, PayableSummary, ReceivableSummary,
)
from commercial.application.product_dto import LowStockProductSummary
from commercial.application.query_dto import (
    CustomerCreditSummary,
    DailySaleSummary,
    OverdueChargeSummary,
    ReceiptSummary,
)


class Permissions:
    def __init__(self) -> None:
        self.allowed = True

    def allows(self, actor, module, action):
        return self.allowed and action == "view"


class Audit:
    def record(self, **event):
        pass


class CommercialQueries:
    def search_products(self, term, *, limit): return ()
    def product_stock(self, product_id): raise AssertionError("não usado")
    def search_customers(self, term, *, limit): return ()

    def customer_credit(self, customer_id):
        return CustomerCreditSummary(customer_id, Decimal("500"), Decimal("125"), Decimal("375"))

    def low_stock_products(self):
        return (LowStockProductSummary(7, "P7", "CAFÉ", Decimal("1"), Decimal("3")),)

    def daily_sales(self, day):
        return (DailySaleSummary(11, None, "VENDA", Decimal("80"), "2026-08-23 10:00", "CONCLUÍDA", False),)

    def daily_receipts(self, day):
        return (ReceiptSummary(21, 99, Decimal("50"), "PIX", "2026-08-23 11:00", "MARIA"),)

    def overdue_charges(self):
        return (OverdueChargeSummary(31, 9, "MARIA", 2, Decimal("40"), date(2026, 8, 1)),)


class FinancialQueries:
    def financial_summary(self, start, end):
        return FinancialSummary(
            Decimal("100"), Decimal("20"), Decimal("70"),
            Decimal("10"), Decimal("50"), Decimal("30"),
        )

    def cash_flow(self, start, end):
        return (CashFlowEntry(
            1, 2, datetime(2026, 8, 23, 12), "ENTRADA", Decimal("50"),
            "VENDA", "dado que não deve sair", "documento secreto",
        ),)

    def receivables(self, **filters):
        return (ReceivableSummary(
            41, 9, "MARIA", "VENDA", "secreto", "DOC-SECRETO",
            "descrição privada", Decimal("100"), Decimal("20"), Decimal("80"),
            date(2026, 8, 1), date(2026, 8, 30), "PARCIAL", False,
        ),)

    def overdue_receivables(self):
        return (ReceivableSummary(
            42, 10, "JOÃO", "VENDA", "secreto", "DOC-ATRASADO",
            "não expor", Decimal("40"), Decimal("0"), Decimal("40"),
            date(2026, 7, 1), date(2026, 8, 1), "ABERTO", True,
        ),)

    def payables(self, **filters):
        return (PayableSummary(
            51, 6, "FORNECEDOR", "COMPRA", "origem", "NF-SECRETA",
            "não expor", Decimal("70"), Decimal("0"), Decimal("70"),
            date(2026, 8, 1), date(2026, 9, 1), "ABERTO",
            bool(filters.get("overdue")), "CENTRO-SECRETO",
        ),)


@dataclass
class Harness:
    permissions: Permissions
    registry: ReadOnlyToolRegistry
    actor: AssistantActor


def _harness() -> Harness:
    permissions = Permissions()
    registry = ReadOnlyToolRegistry(permissions=permissions, audit=Audit())
    register_commercial_read_tools(registry, CommercialQueries())
    register_financial_read_tools(registry, FinancialQueries())
    return Harness(permissions, registry, AssistantActor("operador", "OPERADOR", "sessão"))


def test_consultas_comerciais_devolvem_dtos_minimos():
    harness = _harness()
    credit = harness.registry.execute(ToolRequest("clientes.consultar_credito", {"customer_id": 9}), actor=harness.actor)
    stock = harness.registry.execute(ToolRequest("estoque.listar_baixo", {}), actor=harness.actor)
    sales = harness.registry.execute(ToolRequest("vendas.listar_dia", {"day": "2026-08-23"}), actor=harness.actor)
    receipts = harness.registry.execute(ToolRequest("recebimentos.listar_dia", {"day": "2026-08-23"}), actor=harness.actor)
    charges = harness.registry.execute(ToolRequest("cobrancas.listar_vencidas", {}), actor=harness.actor)

    assert credit.payload == {
        "customer_id": 9, "credit_limit": "500.00",
        "debt_balance": "125.00", "available_credit": "375.00",
    }
    assert set(stock.payload["items"][0]) == {
        "product_id", "code", "description", "current_quantity", "minimum_quantity",
    }
    assert sales.payload["items"][0]["sale_id"] == 11
    assert "access_key" not in sales.payload["items"][0]
    assert "title_id" not in receipts.payload["items"][0]
    assert set(charges.payload["items"][0]) == {
        "installment_id", "customer_id", "customer_name",
        "installment_number", "open_amount", "due_date",
    }


def test_resumo_e_fluxo_minimizam_documentos_e_limitam_periodo():
    harness = _harness()
    summary = harness.registry.execute(ToolRequest("financeiro.resumo", {
        "start_date": "2026-08-01", "end_date": "2026-08-23",
    }), actor=harness.actor)
    flow = harness.registry.execute(ToolRequest("financeiro.fluxo_caixa", {
        "start_date": "2026-08-01", "end_date": "2026-08-23",
    }), actor=harness.actor)
    too_long = harness.registry.execute(ToolRequest("financeiro.resumo", {
        "start_date": "2025-01-01", "end_date": "2026-08-23",
    }), actor=harness.actor)

    assert summary.payload["receivable_open"] == "100.00"
    assert set(flow.payload["items"][0]) == {
        "payment_id", "occurred_at", "direction", "amount", "origin",
    }
    assert "documento secreto" not in str(flow.payload)
    assert not too_long.success


def test_data_invalida_e_permissao_negada_nao_consultam():
    harness = _harness()
    invalid = harness.registry.execute(ToolRequest("vendas.listar_dia", {"day": "23/08/2026"}), actor=harness.actor)
    assert not invalid.success
    harness.permissions.allowed = False
    denied = harness.registry.execute(ToolRequest("estoque.listar_baixo", {}), actor=harness.actor)
    assert not denied.success


def test_servico_financeiro_ausente_nao_registra_ferramentas():
    permissions = Permissions()
    registry = ReadOnlyToolRegistry(permissions=permissions, audit=Audit())
    register_financial_read_tools(registry, None)
    actor = AssistantActor("operador", "OPERADOR", "sessão")
    result = registry.execute(ToolRequest("financeiro.resumo", {
        "start_date": "2026-08-01", "end_date": "2026-08-23",
    }), actor=actor)
    assert not result.success
    assert result.message == "Ferramenta não registrada."


def test_listas_financeiras_sao_limitadas_e_minimizadas():
    harness = _harness()
    receivables = harness.registry.execute(ToolRequest("financeiro.listar_receber", {
        "situation": "ABERTOS",
    }), actor=harness.actor)
    overdue = harness.registry.execute(ToolRequest("financeiro.listar_receber", {
        "situation": "VENCIDOS",
    }), actor=harness.actor)
    payables = harness.registry.execute(ToolRequest("financeiro.listar_pagar", {
        "situation": "ABERTOS",
    }), actor=harness.actor)
    assert receivables.payload["items"][0] == {
        "title_id": 41, "customer_id": 9, "customer_name": "MARIA",
        "open_amount": "80.00", "due_date": "2026-08-30",
        "status": "PARCIAL", "overdue": False,
    }
    assert overdue.payload["items"][0]["title_id"] == 42
    assert payables.payload["items"][0]["beneficiary_id"] == 6
    serialized = str((receivables.payload, payables.payload))
    for forbidden in ("DOC-SECRETO", "NF-SECRETA", "descrição privada", "CENTRO-SECRETO"):
        assert forbidden not in serialized


def test_lista_financeira_recusa_situacao_livre():
    harness = _harness()
    result = harness.registry.execute(ToolRequest("financeiro.listar_pagar", {
        "situation": "TODOS",
    }), actor=harness.actor)
    assert not result.success


def test_intencao_de_pesquisa_nao_seleciona_produto_nem_recebe_id():
    permissions = Permissions()
    registry = DraftToolRegistry(permissions=permissions, audit=Audit())
    register_ui_intent_tools(registry)
    actor = AssistantActor("operador", "OPERADOR", "sessão")

    result = registry.execute(ToolRequest(
        "interface.abrir_pesquisa_produtos", {"term": "café"}
    ), actor=actor)
    invented_id = registry.execute(ToolRequest(
        "interface.abrir_pesquisa_produtos", {"term": "café", "product_id": 7}
    ), actor=actor)

    assert result.success
    assert result.payload == {"action": "OPEN_PRODUCT_SEARCH", "term": "café"}
    assert not invented_id.success
