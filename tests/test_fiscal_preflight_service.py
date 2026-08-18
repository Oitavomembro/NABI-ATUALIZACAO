from dataclasses import dataclass

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


class FakeCatalogService:
    def __init__(self, report=None):
        self.report = report or Catalog()

    def audit(self, *, crt):
        assert crt == 1
        return self.report


class FakeFiscalService:
    TAX_REGIME_CODES = {"SIMPLES_NACIONAL": 1}
    STATE_CODES = {"BA": "29"}

    def __init__(self):
        self.transmitted = False
        self.config = {
            "enabled": True, "default_model": "65", "tax_regime": "SIMPLES_NACIONAL",
            "cnpj": "12345678000195", "state": "BA", "certificate_path": "cert.pfx",
            "issuer": {},
        }

    def load_config(self): return self.config
    def validate_ready(self, **_kwargs): return []
    def inspect_certificate(self, path, password):
        assert (path, password) == ("cert.pfx", "senha")
        return Certificate()
    def _normalize_cnpj(self, value): return value
    def prepare_sale_items(self, items, **_kwargs): return [{"code": "P1"}]
    def build_document_xml(self, **_kwargs): return b"<NFe/>", "1" * 44
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
    assert fiscal.transmitted is False


def test_pre_voo_nao_gera_xml_quando_catalogo_tem_pendencia():
    fiscal = FakeFiscalService()
    catalog = Catalog(total=2, ready=1, blocked=1, ready_product_ids=(7,))
    result = FiscalPreflightService(fiscal, FakeCatalogService(catalog)).run(password="senha")
    assert result.success is False
    assert "1 produto(s)" in result.problems[0]
    assert result.xml_sha256 == ""


def test_pre_voo_detecta_certificado_de_outro_cnpj():
    fiscal = FakeFiscalService()
    fiscal.inspect_certificate = lambda *_args: Certificate(document="99999999000199")
    result = FiscalPreflightService(fiscal, FakeCatalogService()).run(password="senha")
    assert result.success is False
    assert any("não corresponde" in problem for problem in result.problems)
