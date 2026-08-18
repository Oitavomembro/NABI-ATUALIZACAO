import pytest

from services.fiscal_rtc_resolver import FiscalRtcResolver


def regular_profile(**changes):
    profile = {
        "ibs_cbs_cst": "000", "ibs_cbs_class": "000001",
        "ibs_uf_rate": "0.1", "ibs_city_rate": "0", "cbs_rate": "0.9",
    }
    profile.update(changes)
    return profile


def test_venda_nacional_regular_preserva_aliquotas_rastreaveis():
    rule = FiscalRtcResolver.resolve(regular_profile(), destination=1)
    assert rule.taxable is True
    assert (rule.cst, rule.classification) == ("000", "000001")
    assert (rule.ibs_uf_rate, rule.ibs_city_rate, rule.cbs_rate) == ("0.1", "0", "0.9")


def test_exportacao_aplica_nao_incidencia_oficial_sem_aliquota_inventada():
    rule = FiscalRtcResolver.resolve(regular_profile(), destination=3)
    assert rule.taxable is False
    assert (rule.cst, rule.classification) == ("410", "410004")
    assert (rule.ibs_uf_rate, rule.ibs_city_rate, rule.cbs_rate) == ("0", "0", "0")


@pytest.mark.parametrize(
    "cst,classification",
    [("200", "200001"), ("410", "410001"), ("000", "000999")],
)
def test_regime_especial_nao_e_aceito_como_venda_regular(cst, classification):
    with pytest.raises(ValueError, match="Regimes especiais"):
        FiscalRtcResolver.resolve(
            regular_profile(ibs_cbs_cst=cst, ibs_cbs_class=classification), destination=1
        )
