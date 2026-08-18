from decimal import Decimal

import pytest

from services.fiscal_product_profile import FiscalProductProfile


def complete_profile(**changes):
    values = {
        "ncm": "94036000", "cest": "", "cfop": "5102", "fiscal_origin": "0",
        "fiscal_csosn": "102", "fiscal_icms_cst": "", "fiscal_icms_rate": "0",
        "fiscal_pis_cst": "07", "fiscal_pis_rate": "0",
        "fiscal_cofins_cst": "07", "fiscal_cofins_rate": "0",
        "ibs_cbs_cst": "000", "ibs_cbs_class": "000001",
        "ibs_uf_rate": "0.1", "ibs_city_rate": "0", "cbs_rate": "0.9",
    }
    values.update(changes)
    return values


def test_simples_exige_csosn_e_aceita_origem_zero():
    profile = FiscalProductProfile.validate_for_regime(
        complete_profile(), crt=1, require_rtc=True
    )
    assert profile["fiscal_origin"] == "0"
    assert profile["fiscal_csosn"] == "102"


def test_regime_normal_exige_cst_icms_em_vez_de_csosn():
    profile = FiscalProductProfile.validate_for_regime(
        complete_profile(fiscal_csosn="", fiscal_icms_cst="00", fiscal_icms_rate="18"),
        crt=3, require_rtc=True,
    )
    assert profile["fiscal_icms_cst"] == "00"
    assert Decimal(profile["fiscal_icms_rate"]) == Decimal("18")


@pytest.mark.parametrize("field", ["fiscal_pis_cst", "fiscal_cofins_cst"])
def test_contribuicoes_nao_podem_ficar_sem_classificacao(field):
    with pytest.raises(ValueError, match="incompleta"):
        FiscalProductProfile.validate_for_regime(
            complete_profile(**{field: ""}), crt=1, require_rtc=True
        )


def test_rejeita_codigo_e_aliquota_fora_da_matriz():
    with pytest.raises(ValueError, match="CSOSN"):
        FiscalProductProfile.normalize(complete_profile(fiscal_csosn="999"))
    with pytest.raises(ValueError, match="entre 0 e 100"):
        FiscalProductProfile.normalize(complete_profile(fiscal_pis_rate="101"))


@pytest.mark.parametrize(
    "changes,crt",
    [
        ({"fiscal_csosn": "500", "cest": ""}, 1),
        ({"fiscal_csosn": "", "fiscal_icms_cst": "60", "cest": ""}, 3),
    ],
)
def test_substituicao_tributaria_exige_cest(changes, crt):
    with pytest.raises(ValueError, match="CEST"):
        FiscalProductProfile.validate_for_regime(
            complete_profile(**changes), crt=crt, require_rtc=True
        )


def test_origem_da_ficha_nao_e_inventada_pela_normalizacao():
    assert FiscalProductProfile.normalize(complete_profile())["fiscal_profile_source"] == ""
