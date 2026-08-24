from decimal import Decimal

from assistant_nabi import AssistantActor, ReadOnlyToolRegistry, ToolRequest
from assistant_nabi.report_tools import register_report_read_tools
from commercial.application.report_dto import ReportIndicators


class Permissions:
    def __init__(self, allowed=True): self.allowed = allowed
    def allows(self, actor, module, action):
        return self.allowed and module == "relatorios" and action == "view"


class Audit:
    def record(self, **event): pass


class Reports:
    def __init__(self): self.calls = []
    def indicators(self, start, end):
        self.calls.append((start, end))
        return ReportIndicators(
            Decimal("120.50"), Decimal("80.00"), Decimal("30.25"), 4, 17
        )


def harness(*, allowed=True, reports=None):
    permissions = Permissions(allowed)
    registry = ReadOnlyToolRegistry(permissions=permissions, audit=Audit())
    register_report_read_tools(registry, reports)
    return registry, AssistantActor("operador", "OPERADOR", "sessao")


def test_indicadores_expoem_somente_totais_agregados():
    reports = Reports()
    registry, actor = harness(reports=reports)
    result = registry.execute(ToolRequest("relatorios.consultar_indicadores", {
        "start_date": "2026-08-01", "end_date": "2026-08-24",
    }), actor=actor)
    assert result.success
    assert reports.calls == [("2026-08-01", "2026-08-24")]
    assert result.payload == {
        "start_date": "2026-08-01", "end_date": "2026-08-24",
        "sales_total": "120.50", "receivable_open": "80.00",
        "payable_open": "30.25", "low_stock": 4, "active_customers": 17,
    }


def test_periodos_invalidos_nao_consultam_servico():
    for start, end in (
        ("24/08/2026", "2026-08-24"),
        ("2026-08-25", "2026-08-24"),
        ("2025-01-01", "2026-08-24"),
    ):
        reports = Reports()
        registry, actor = harness(reports=reports)
        result = registry.execute(ToolRequest("relatorios.consultar_indicadores", {
            "start_date": start, "end_date": end,
        }), actor=actor)
        assert not result.success
        assert reports.calls == []


def test_permissao_negada_nao_consulta_servico():
    reports = Reports()
    registry, actor = harness(allowed=False, reports=reports)
    result = registry.execute(ToolRequest("relatorios.consultar_indicadores", {
        "start_date": "2026-08-01", "end_date": "2026-08-24",
    }), actor=actor)
    assert not result.success
    assert reports.calls == []


def test_servico_ausente_nao_registra_ferramenta():
    registry, actor = harness(reports=None)
    result = registry.execute(ToolRequest("relatorios.consultar_indicadores", {
        "start_date": "2026-08-01", "end_date": "2026-08-24",
    }), actor=actor)
    assert not result.success
    assert result.message == "Ferramenta não registrada."


def test_ferramenta_nao_expoe_geracao_exportacao_ou_fiscal():
    source = __import__("pathlib").Path("assistant_nabi/report_tools.py").read_text("utf-8")
    assert ".generate(" not in source
    assert ".export(" not in source
    assert "fiscal" not in source.casefold()
    assert "sefaz" not in source.casefold()
