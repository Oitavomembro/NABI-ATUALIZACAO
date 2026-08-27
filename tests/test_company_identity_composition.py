from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ui_qt.administration.composition import _company_identity_provider


def _profile(**changes):
    values = {
        "version": 4,
        "cnpj": "12.345.678/0001-95",
        "legal_name": "EMPRESA TESTE LTDA",
        "trade_name": "LOJA TESTE",
    }
    values.update(changes)
    service = Mock()
    service.active.return_value = SimpleNamespace(**values)
    return service


def test_perfil_empresarial_vigente_e_a_fonte_canonica_na_edicao_comercial():
    identity = _company_identity_provider(Mock(), None, _profile())()

    assert identity.cnpj == "12345678000195"
    assert identity.legal_name == "LOJA TESTE"
    assert identity.source == "perfil empresarial confirmado v4"


def test_edicao_fiscal_exige_concordancia_entre_perfil_configuracao_e_a1():
    fiscal = Mock()
    fiscal.load_config.return_value = {
        "cnpj": "12.345.678/0001-95",
        "certificate_info": {"document": "12.345.678/0001-95"},
    }

    identity = _company_identity_provider(Mock(), fiscal, _profile())()

    assert identity.cnpj == "12345678000195"
    fiscal.load_config.assert_called_once_with()


@pytest.mark.parametrize("configured,certificate", [
    ("99.999.999/0001-99", "12.345.678/0001-95"),
    ("12.345.678/0001-95", "99.999.999/0001-99"),
    ("", "12.345.678/0001-95"),
])
def test_divergencia_fiscal_bloqueia_o_pacote_contabil(configured, certificate):
    fiscal = Mock()
    fiscal.load_config.return_value = {
        "cnpj": configured,
        "certificate_info": {"document": certificate},
    }

    with pytest.raises(RuntimeError, match="diverge|Configure"):
        _company_identity_provider(Mock(), fiscal, _profile())()


def test_razao_social_e_usada_quando_nome_fantasia_nao_existe():
    identity = _company_identity_provider(
        Mock(), None, _profile(trade_name=""),
    )()

    assert identity.legal_name == "EMPRESA TESTE LTDA"
