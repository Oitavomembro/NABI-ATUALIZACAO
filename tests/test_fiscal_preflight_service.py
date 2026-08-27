from dataclasses import dataclass
from types import SimpleNamespace

from services.fiscal_preflight_service import FiscalPreflightService


@dataclass
class Certificate:
    document: str = "12345678000195"
    expired: bool = False


@dataclass
class Catalog:
    total: int = 1
    ready: int = 1
    blocked: int = 0
    ready_product_ids: tuple[int, ...] = (7,)
    issues: tuple = ()


@dataclass
class Trust:
    trusted: bool = True
    message: str = "Cadeia válida."


class FakeCatalogService:
    def __init__(self, report=None):
        self.report = report or Catalog()

    def audit(self, *, crt):
        assert crt == 1
        return self.report


class FakeFiscalService:
    TAX_REGIME_CODES = {"SIMPLES_NACIONAL": 1}
    STATE_CODES = {"BA": "29"}
    HOMOLOGATION_RECIPIENT_NAME = (
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    )
    HOMOLOGATION_RECIPIENT_CNPJ = "99999999000191"

    def __init__(self):
        self.transmitted = False
        self.built_models = []
        self.config = {
            "enabled": True, "default_model": "65", "tax_regime": "SIMPLES_NACIONAL",
            "enabled_models": ["55", "65"],
            "cnpj": "12345678000195", "state": "BA", "certificate_path": "cert.pfx",
            "issuer": {},
        }

    def load_config(self): return self.config
    def validate_ready(self, **_kwargs): return []
    def inspect_certificate(self, path, password):
        assert (path, password) == ("cert.pfx", "senha")
        return Certificate()
    def validate_certificate_trust(self, path, password):
        assert (path, password) == ("cert.pfx", "senha")
        return Trust()
    def _normalize_cnpj(self, value): return value
    def prepare_sale_items(self, items, **_kwargs): return [{"code": "P1"}]
    def build_document_xml(self, **kwargs):
        self.built_models.append(kwargs["document"]["model"])
        if kwargs["document"]["model"] == "55":
            assert kwargs["recipient"]["name"] == self.HOMOLOGATION_RECIPIENT_NAME
            assert kwargs["recipient"]["document"] == self.HOMOLOGATION_RECIPIENT_CNPJ
        return b"<NFe/>", "1" * 44
    def sign_xml(self, xml, **_kwargs): return b"<NFe signed='1'/>"
    def official_schema_path(self, _kind): return "nfe.xsd"
    def validate_xml_schema(self, xml, schema):
        assert xml == b"<NFe signed='1'/>" and schema == "nfe.xsd"
        return []


def test_pre_voo_assina_e_valida_localmente_sem_transmitir():
    fiscal = FakeFiscalService()
    result = FiscalPreflightService(fiscal, FakeCatalogService()).run(password="senha")
    assert result.success is True
    assert result.catalog_ready == 1
    assert result.certificate_document == "12345678000195"
    assert len(result.xml_sha256) == 64
    assert result.validated_models == ("55", "65")
    assert len(result.xml_sha256_by_model) == 2
    assert fiscal.built_models == ["55", "65"]
    assert fiscal.transmitted is False


def test_pre_voo_nao_gera_xml_quando_catalogo_tem_pendencia():
    fiscal = FakeFiscalService()
    catalog = Catalog(total=2, ready=1, blocked=1, ready_product_ids=(7,))
    result = FiscalPreflightService(fiscal, FakeCatalogService(catalog)).run(password="senha")
    assert result.success is False
    assert "1 produto(s)" in result.problems[0]
    assert result.xml_sha256 == ""


def test_pre_voo_identifica_produto_e_pendencia_exata():
    fiscal = FakeFiscalService()
    issue = SimpleNamespace(code="ABC", name="BISCOITO", message="ficha fiscal incompleta — CFOP.")
    catalog = Catalog(total=1, ready=0, blocked=1, ready_product_ids=(), issues=(issue,))
    result = FiscalPreflightService(fiscal, FakeCatalogService(catalog)).run(password="senha")
    assert any("Produto ABC" in problem and "CFOP" in problem for problem in result.problems)


def test_pre_voo_detecta_certificado_de_outro_cnpj():
    fiscal = FakeFiscalService()
    fiscal.inspect_certificate = lambda *_args: Certificate(document="99999999000199")
    result = FiscalPreflightService(fiscal, FakeCatalogService()).run(password="senha")
    assert result.success is False
    assert any("não corresponde" in problem for problem in result.problems)


def test_pre_voo_rejeita_certificado_sem_cadeia_icp_brasil():
    fiscal = FakeFiscalService()
    fiscal.validate_certificate_trust = lambda *_args: Trust(
        trusted=False, message="Emissor não encontrado."
    )
    result = FiscalPreflightService(fiscal, FakeCatalogService()).run(password="senha")
    assert result.success is False
    assert any("Cadeia ICP-Brasil" in problem for problem in result.problems)


def test_pre_voo_reprova_conjunto_quando_um_modelo_falha():
    fiscal = FakeFiscalService()
    fiscal.validate_ready = lambda **kwargs: (
        ["modelo indisponível"] if kwargs["model"] == "55" else []
    )
    result = FiscalPreflightService(fiscal, FakeCatalogService()).run(password="senha")
    assert result.success is False
    assert result.validated_models == ()
    assert any("NF-e 55: modelo indisponível" == problem for problem in result.problems)
    assert fiscal.built_models == []


def test_pre_voo_respeita_somente_modelo_habilitado():
    fiscal = FakeFiscalService()
    fiscal.config.update({"enabled_models": ["55"], "default_model": "55"})
    result = FiscalPreflightService(fiscal, FakeCatalogService()).run(password="senha")
    assert result.success is True
    assert result.validated_models == ("55",)
    assert fiscal.built_models == ["55"]


def test_pre_voo_recusa_configuracao_de_producao():
    fiscal = FakeFiscalService()
    fiscal.config["environment"] = "PRODUCAO"
    result = FiscalPreflightService(fiscal, FakeCatalogService()).run(password="senha")
    assert result.success is False
    assert any("só pode ser executado" in problem for problem in result.problems)
    assert fiscal.built_models == []
