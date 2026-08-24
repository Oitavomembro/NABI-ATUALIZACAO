from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from services.tax_projection_service import (
    TaxProjectionRule,
    TaxProjectionService,
    TaxRevenueSegment,
)


def rule(**changes) -> TaxProjectionRule:
    values = {
        "rule_id": "SN-ANEXO-I-FAIXA-4",
        "version": "contador-2026-01",
        "annex": "I",
        "nominal_rate_percent": Decimal("10.70"),
        "deduction": Decimal("22500.00"),
        "effective_from": date(2026, 1, 1),
        "effective_until": date(2026, 12, 31),
        "source": "Manual PGDAS-D e confirmação contábil",
        "confirmed_by": "Contabilidade responsável",
        "confirmed_at": datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
    }
    values.update(changes)
    return TaxProjectionRule(**values)


def project(**changes):
    values = {
        "period_start": date(2026, 8, 1),
        "period_end": date(2026, 8, 31),
        "calculated_through": date(2026, 8, 10),
        "rbt12": Decimal("1500000.00"),
        "segments": [TaxRevenueSegment("REVENDA", "Revenda comum", Decimal("120000"), rule())],
        "recognition_basis": "COMPETENCIA",
    }
    values.update(changes)
    return TaxProjectionService().project_simple_national(**values)


def test_calcula_formula_oficial_com_memoria_e_reserva():
    result = project()
    assert result.estimated_tax_to_date == Decimal("11040.00")
    assert result.weighted_effective_rate_percent == Decimal("9.200000")
    assert result.projected_month_revenue == Decimal("372000.00")
    assert result.projected_month_tax == Decimal("34224.00")
    assert result.recommended_reserve == Decimal("35935.20")
    assert result.official_assessment is False
    assert result.segments[0].rule_version == "contador-2026-01"
    assert result.segments[0].source


def test_totaliza_segregacoes_sem_perder_memoria_individual():
    second = rule(
        rule_id="SN-OUTRA-SEGREGACAO", nominal_rate_percent=Decimal("6"), deduction=Decimal("0")
    )
    result = project(segments=[
        TaxRevenueSegment("REVENDA", "Revenda", Decimal("1000"), rule()),
        TaxRevenueSegment("OUTRA", "Outra receita", Decimal("500"), second),
    ])
    assert result.revenue_to_date == Decimal("1500.00")
    assert result.estimated_tax_to_date == Decimal("122.00")
    assert len(result.segments) == 2


@pytest.mark.parametrize("basis", ["CAIXA", "COMPETENCIA", "caixa"])
def test_aceita_somente_bases_de_reconhecimento_explicitas(basis):
    assert project(recognition_basis=basis).recognition_basis == basis.upper()


def test_bloqueia_regra_sem_fonte_ou_confirmacao():
    with pytest.raises(ValueError, match="Regra tributária incompleta"):
        project(segments=[TaxRevenueSegment("A", "A", Decimal("10"), rule(source=""))])


def test_bloqueia_regra_fora_da_vigencia():
    with pytest.raises(ValueError, match="não está vigente"):
        project(segments=[TaxRevenueSegment(
            "A", "A", Decimal("10"), rule(effective_until=date(2026, 7, 31))
        )])


def test_bloqueia_codigo_repetido_e_receita_negativa():
    with pytest.raises(ValueError, match="código único"):
        project(segments=[
            TaxRevenueSegment("A", "A", Decimal("10"), rule()),
            TaxRevenueSegment("a", "B", Decimal("20"), rule(rule_id="B")),
        ])
    with pytest.raises(ValueError, match="não pode ser negativa"):
        project(segments=[TaxRevenueSegment("A", "A", Decimal("-1"), rule())])


def test_rbt12_zero_e_consulta_parcial_geram_alertas_explicitos():
    zero_rule = rule(nominal_rate_percent=Decimal("4"), deduction=Decimal("0"))
    result = project(
        rbt12=0,
        segments=[TaxRevenueSegment("ABERTURA", "Início", Decimal("100"), zero_rule)],
    )
    assert result.estimated_tax_to_date == Decimal("4.00")
    assert any("início de atividade" in warning for warning in result.warnings)
    assert any("média diária" in warning for warning in result.warnings)


def test_fechamento_do_mes_nao_extrapola_receita():
    result = project(calculated_through=date(2026, 8, 31))
    assert result.projected_month_revenue == result.revenue_to_date
    assert result.projected_month_tax == result.estimated_tax_to_date
    assert not any("média diária" in warning for warning in result.warnings)


def test_nao_aceita_float_infinito_nem_resultado_negativo():
    with pytest.raises(ValueError, match="deve ser finito"):
        project(rbt12=float("inf"))
    impossible = rule(nominal_rate_percent=Decimal("1"), deduction=Decimal("999999"))
    with pytest.raises(ValueError, match="fora de 0% a 100%"):
        project(segments=[TaxRevenueSegment("A", "A", Decimal("1"), impossible)])
