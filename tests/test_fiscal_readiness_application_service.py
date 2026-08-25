from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography import x509
from cryptography.x509.oid import ObjectIdentifier

from administration.fiscal_readiness_application_service import (
    FiscalReadinessApplicationService,
)
from services.fiscal_service import FiscalService


@dataclass
class Certificate:
    document: str = "47584215000160"
    expired: bool = False


class Security:
    def __init__(self, allowed=True):
        self.session = object(); self.allowed = allowed; self.touched = 0
    def is_expired(self): return False
    def require(self, module, action):
        assert module == "fiscal"; return self.allowed
    def touch(self): self.touched += 1


class Fiscal:
    STATE_CODES = {"BA": "29"}
    TAX_REGIME_LABELS = {"SIMPLES_NACIONAL": "Simples Nacional"}
    MODEL_LABELS = {"55": "NF-e", "65": "NFC-e"}
    def __init__(self):
        self.saved = None; self.cached = None
        self.config = {
            "enabled": False, "environment": "HOMOLOGACAO", "cnpj": "",
            "state": "BA", "tax_regime": "SIMPLES_NACIONAL",
            "enabled_models": ["55", "65"], "default_model": "65",
            "sale_series_55": 1, "sale_series_65": 1,
            "certificate_path": "", "issuer": {},
        }
    def load_config(self): return dict(self.config)
    def validate_ready(self, **_kwargs): return ["Configuração incompleta"]
    def numbering_scope(self, **_kwargs): return {"initialized": False}
    def inspect_certificate(self, path, password):
        assert path == "empresa.pfx" and password == "segredo"; return Certificate()
    def save_config(self, values):
        assert "password" not in values and "senha" not in values
        self.saved = dict(values); self.config.update(values); return dict(self.config)
    def cache_certificate_password(self, password): self.cached = password
    def session_certificate_password(self): return self.cached


def values():
    return {
        "cnpj": "47.584.215/0001-60", "certificate_path": "empresa.pfx",
        "state": "BA", "tax_regime": "SIMPLES_NACIONAL",
        "model_55": True, "model_65": True, "default_model": "65",
        "sale_series_55": 1, "sale_series_65": 1, "issuer_name": "Empresa",
    }


def test_configura_somente_homologacao_e_nao_persiste_senha():
    fiscal = Fiscal(); service = FiscalReadinessApplicationService(fiscal, Security())
    saved = service.configure_homologation(values(), password="segredo")
    assert saved["environment"] == "HOMOLOGACAO"
    assert fiscal.saved["cnpj"] == "47584215000160"
    assert fiscal.cached == "segredo"
    assert "segredo" not in repr(fiscal.saved)


def test_cnpj_digitado_nao_substitui_identidade_do_certificado():
    fiscal = Fiscal(); service = FiscalReadinessApplicationService(fiscal, Security())
    data = values(); data["cnpj"] = "12345678000195"
    service.configure_homologation(data, password="segredo")
    assert fiscal.saved["cnpj"] == Certificate().document


def test_configuracao_exige_permissao_real():
    fiscal = Fiscal(); service = FiscalReadinessApplicationService(fiscal, Security(False))
    with pytest.raises(PermissionError):
        service.configure_homologation(values(), password="segredo")
    assert fiscal.saved is None


def test_leitor_prioriza_cnpj_oficial_icp_brasil_sobre_numeros_do_responsavel():
    certificate = SimpleNamespace(
        extensions=Mock(),
        subject=[SimpleNamespace(value="RESPONSAVEL:12345678901234")],
    )
    san = x509.SubjectAlternativeName([
        x509.OtherName(
            ObjectIdentifier("2.16.76.1.3.3"),
            b"\x0c\x0e47584215000160",
        )
    ])
    certificate.extensions.get_extension_for_class.return_value.value = san
    assert FiscalService._document_from_certificate(certificate) == "47584215000160"


def test_pre_voo_usa_senha_somente_da_sessao_e_nao_recebe_segredo_da_gui():
    fiscal = Fiscal(); fiscal.cached = "segredo-em-memoria"
    service = FiscalReadinessApplicationService(fiscal, Security())
    service._preflight = Mock(); service._preflight.run.return_value = object()
    result = service.run_local_preflight()
    assert result is service._preflight.run.return_value
    service._preflight.run.assert_called_once_with(password="segredo-em-memoria")
