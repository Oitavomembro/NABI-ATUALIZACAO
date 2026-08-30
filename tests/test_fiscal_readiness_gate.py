from types import SimpleNamespace

import pytest

from services.fiscal_dfe_service import FiscalDFeService
from services.fiscal_readiness_gate import FiscalReadinessGate
from services.fiscal_sale_service import FiscalSaleService
from services.fiscal_service import FiscalService


class Catalog:
    def __init__(self, *, total=1, blocked=0):
        self.total = total
        self.blocked = blocked

    def audit(self, **_kwargs):
        return SimpleNamespace(total=self.total, blocked=self.blocked)


class Regulatory:
    def __init__(self, *problems):
        self.problems = tuple(problems)

    def audit(self, **_kwargs):
        return SimpleNamespace(problems=self.problems)


class GateFiscal:
    TAX_REGIME_CODES = {"SIMPLES": 1}

    def __init__(self):
        self.config = {
            "enabled": True, "environment": "HOMOLOGACAO",
            "cnpj": "12345678000195", "tax_regime": "SIMPLES",
            "certificate_path": "certificado.pfx",
        }

    def load_config(self): return dict(self.config)
    def validate_ready(self, **_kwargs): return []
    def inspect_certificate(self, *_args):
        return SimpleNamespace(expired=False, document="12345678000195")
    def validate_certificate_trust(self, *_args):
        return SimpleNamespace(trusted=True, message="ok")
    def check_certificate_revocation(self, *_args):
        return SimpleNamespace(good=True, message="ok")
    def numbering_scope(self, **_kwargs): return {"initialized": True}
    @staticmethod
    def _normalize_cnpj(value): return str(value)


def test_gate_rejeita_a1_de_outro_cnpj_catalogo_e_numeracao_pendentes():
    fiscal = GateFiscal()
    fiscal.inspect_certificate = lambda *_args: SimpleNamespace(
        expired=False, document="99999999000199"
    )
    fiscal.numbering_scope = lambda **_kwargs: {"initialized": False}
    result = FiscalReadinessGate(
        fiscal, Catalog(total=1, blocked=1), Regulatory()
    ).evaluate(
        operation="autorizacao", model="65", password="senha", series=1,
        require_catalog=True, require_numbering=True,
    )
    assert not result.ready
    assert any("não corresponde" in problem for problem in result.problems)
    assert any("numeração" in problem for problem in result.problems)
    assert any("pendência fiscal" in problem for problem in result.problems)


def test_venda_nao_reserva_numero_quando_portao_recusa():
    class Fiscal:
        TAX_REGIME_CODES = {"SIMPLES": 1}
        reservations = 0
        def load_config(self):
            return {"default_model": "65", "tax_regime": "SIMPLES", "state": "BA"}
        def validate_ready(self, **_kwargs): return []
        def prepare_sale_items(self, *_args, **_kwargs): return [{"description": "P"}]
        def session_certificate_password(self): return "senha"
        def require_operational_readiness(self, **_kwargs):
            raise ValueError("configuração fiscal incompleta")
        def reserve_number(self, **_kwargs):
            self.reservations += 1

    fiscal = Fiscal()
    with pytest.raises(ValueError, match="incompleta"):
        FiscalSaleService(fiscal).prepare(items=[{"produto_id": 1}], payments=[])
    assert fiscal.reservations == 0


def test_dfe_nao_abre_rede_quando_portao_recusa(tmp_path):
    class Fiscal:
        http_calls = 0
        STATE_CODES = {"BA": "29"}
        def load_config(self):
            return {"environment": "HOMOLOGACAO", "cnpj": "12345678000195", "state": "BA"}
        def require_operational_readiness(self, **_kwargs):
            raise ValueError("A1 inválido")

    fiscal = Fiscal()
    service = FiscalDFeService(fiscal, storage_dir=tmp_path)
    with pytest.raises(ValueError, match="A1 inválido"):
        service.fetch_next(password="senha")
    assert fiscal.http_calls == 0


def test_servico_fiscal_sem_gate_falha_fechado_antes_de_autenticar():
    fiscal = object.__new__(FiscalService)
    fiscal._readiness_enforced = False
    fiscal._readiness_gate = None
    authenticated = []
    fiscal._authenticated_fiscal_actor = lambda *_args, **_kwargs: authenticated.append(True)

    with pytest.raises(PermissionError, match="portão de prontidão fiscal"):
        fiscal.require_operational_readiness(
            operation="autorizacao", model="65", password="",
            permission="fiscal/transmit",
        )
    assert authenticated == []


def test_tentativa_de_bypass_por_flag_sem_gate_tambem_falha_fechado():
    fiscal = object.__new__(FiscalService)
    fiscal._readiness_enforced = True
    fiscal._readiness_gate = None
    fiscal._authenticated_fiscal_actor = lambda *_args, **_kwargs: "ator"

    with pytest.raises(PermissionError, match="nenhuma operação Fiscal/SEFAZ"):
        fiscal.require_operational_readiness(
            operation="evento", model="55", password="senha",
            permission="fiscal/transmit",
        )


def test_gate_limpo_exige_cnpj_certificado_e_configuracao():
    fiscal = GateFiscal()
    fiscal.config.update({"cnpj": "", "certificate_path": "", "tax_regime": ""})
    fiscal.validate_ready = lambda **_kwargs: [
        "CNPJ obrigatório", "certificado obrigatório", "regime obrigatório"
    ]
    fiscal.inspect_certificate = lambda *_args: (_ for _ in ()).throw(
        ValueError("certificado A1 não configurado")
    )

    result = FiscalReadinessGate(fiscal).evaluate(
        operation="status", model="55", password=""
    )
    assert not result.ready
    assert any("CNPJ obrigatório" in problem for problem in result.problems)
    assert any("certificado" in problem for problem in result.problems)
    assert any("regime obrigatório" in problem for problem in result.problems)


def test_gate_rejeita_catalogo_regulatorio_ausente_ou_vencido():
    fiscal = GateFiscal()
    missing = FiscalReadinessGate(fiscal, Catalog()).evaluate(
        operation="status", model="55", password="senha"
    )
    expired = FiscalReadinessGate(
        fiscal, Catalog(), Regulatory("Revisão regulatória vencida")
    ).evaluate(operation="status", model="55", password="senha")

    assert any("não está configurado" in problem for problem in missing.problems)
    assert any("Revisão regulatória vencida" in problem for problem in expired.problems)
