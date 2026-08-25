import base64
import gzip
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.fiscal_dfe_service import FiscalDFeService


VALID_CNPJ = "12345678000195"


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class FakeFiscal:
    STATE_CODES = {"BA": "29"}

    def __init__(self, response=b""):
        self.response = response
        self.calls = []
        self._db_uri = f"file:dfe-fake-{uuid.uuid4().hex}?mode=memory&cache=shared"
        self._keeper = sqlite3.connect(self._db_uri, uri=True)
        self._keeper.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        self._keeper.commit()

    def connection_factory(self):
        return sqlite3.connect(self._db_uri, uri=True)

    _normalize_cnpj = staticmethod(lambda value: "".join(c for c in str(value or "") if c.isdigit()))
    _is_valid_cnpj = staticmethod(lambda value: value == VALID_CNPJ)
    _normalize_access_key = staticmethod(lambda value: "".join(c for c in str(value or "") if c.isdigit()))
    _is_valid_access_key = staticmethod(lambda value: len(value) == 44)

    def _get_setting(self, key):
        connection = self.connection_factory()
        try:
            row = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (key,)
            ).fetchone()
            return "" if row is None else row[0]
        finally:
            connection.close()

    def _set_setting(self, key, value):
        connection = self.connection_factory()
        try:
            connection.execute(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES (?,?)",
                (key, value),
            )
            connection.commit()
        finally:
            connection.close()

    def load_config(self):
        return {
            "environment": "HOMOLOGACAO", "cnpj": VALID_CNPJ,
            "state": "BA", "certificate_path": "fake.pfx",
        }

    def require_operational_readiness(self, **_kwargs):
        return "auditor"

    def inspect_certificate(self, _path, _password):
        return SimpleNamespace(document=VALID_CNPJ)

    def validate_certificate_trust(self, _path, _password):
        return SimpleNamespace(trusted=True, message="ok")

    def check_certificate_revocation(self, _path, _password):
        return SimpleNamespace(good=True, message="ok")

    def _temporary_pem_files(self, _path, _password):
        return "fake-cert.pem", "fake-key.pem"

    def _secure_delete_file(self, _path):
        return None


def response_xml(*, last="1", maximum="1", environment="2", content=None):
    document = ""
    if content is not None:
        payload = base64.b64encode(gzip.compress(content)).decode("ascii")
        document = f'<loteDistDFeInt><docZip NSU="{last}" schema="resNFe_v1.00.xsd">{payload}</docZip></loteDistDFeInt>'
    return (
        f'<retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">'
        f'<tpAmb>{environment}</tpAmb><cStat>{"138" if content else "137"}</cStat>'
        f'<xMotivo>fake</xMotivo><ultNSU>{last}</ultNSU><maxNSU>{maximum}</maxNSU>'
        f'{document}</retDistDFeInt>'
    ).encode()


def test_ambiente_e_origem_sao_fechados(tmp_path):
    service = FiscalDFeService(FakeFiscal(), storage_dir=tmp_path)
    with pytest.raises(ValueError, match="Ambiente DF-e"):
        service.build_request(cnpj=VALID_CNPJ, state_code="29", environment="TESTE", last_nsu="0")
    with pytest.raises(ValueError, match="origem"):
        service.parse_response(
            response_xml(), expected_environment="HOMOLOGACAO",
            origin_url="https://exemplo.invalid/dfe",
        )


def test_transporte_fake_recebe_exclusivamente_endpoint_oficial(tmp_path):
    fiscal = FakeFiscal(response_xml())

    def transport(url, **kwargs):
        fiscal.calls.append((url, kwargs))
        return FakeResponse(fiscal.response)

    service = FiscalDFeService(fiscal, storage_dir=tmp_path, transport=transport)
    result = service.fetch_next(password="segredo-falso")

    assert result.status_code == "137"
    assert fiscal.calls[0][0] == service.ENDPOINTS["HOMOLOGACAO"]


def test_cnpj_do_certificado_divergente_falha_antes_do_transporte(tmp_path):
    fiscal = FakeFiscal(response_xml())
    fiscal.inspect_certificate = lambda *_args: SimpleNamespace(document="11222333000181")
    calls = []
    service = FiscalDFeService(fiscal, storage_dir=tmp_path, transport=lambda *_a, **_k: calls.append(1))

    with pytest.raises(ValueError, match="CNPJ do certificado"):
        service.fetch_next(password="segredo-falso")
    assert calls == []


def test_nsu_retrogrado_duplicado_ou_acima_do_lote_falha_fechado(tmp_path):
    fiscal = FakeFiscal()
    service = FiscalDFeService(fiscal, storage_dir=tmp_path)
    fiscal._set_setting(service.CONFIG_KEY, json.dumps({"last_nsu": "10", "max_nsu": "10"}))

    with pytest.raises(ValueError, match="regredir"):
        service.parse_response(response_xml(last="9", maximum="10"))
    content = b'<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00"/>'
    payload = base64.b64encode(gzip.compress(content)).decode("ascii")
    duplicate = (
        '<retDistDFeInt versao="1.01"><tpAmb>2</tpAmb><cStat>138</cStat>'
        '<ultNSU>11</ultNSU><maxNSU>11</maxNSU><loteDistDFeInt>'
        f'<docZip NSU="11" schema="resNFe_v1.00.xsd">{payload}</docZip>'
        f'<docZip NSU="11" schema="resNFe_v1.00.xsd">{payload}</docZip>'
        '</loteDistDFeInt></retDistDFeInt>'
    )
    with pytest.raises(ValueError, match="repete o NSU"):
        service.parse_response(duplicate)


def test_schema_raiz_hash_origem_e_idempotencia(tmp_path):
    fiscal = FakeFiscal()
    service = FiscalDFeService(fiscal, storage_dir=tmp_path)
    content = b'<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00"/>'
    origin = service.ENDPOINTS["HOMOLOGACAO"]
    xml = response_xml(content=content)

    first = service.parse_response(xml, expected_environment="HOMOLOGACAO", origin_url=origin)
    second = service.parse_response(xml, expected_environment="HOMOLOGACAO", origin_url=origin)
    index = json.loads(fiscal._get_setting(service.INDEX_KEY))

    assert first.documents[0]["sha256"] == hashlib.sha256(content).hexdigest()
    assert second.documents[0]["sha256"] == first.documents[0]["sha256"]
    assert len(index) == 1
    assert index[0]["origin"] == origin
    assert index[0]["environment"] == "HOMOLOGACAO"
    assert index[0]["received_by"] == "NAO_INFORMADO"
    assert index[0]["received_at"]
    assert Path(index[0]["path"]).read_bytes() == content

    wrong_root = b'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"/>'
    with pytest.raises(ValueError, match="schema declarado"):
        service.parse_response(response_xml(last="2", maximum="2", content=wrong_root))


def test_falha_no_indice_reverte_cursor_e_remove_arquivo_novo(tmp_path):
    fiscal = FakeFiscal()
    service = FiscalDFeService(fiscal, storage_dir=tmp_path)
    connection = fiscal.connection_factory()
    connection.execute(f"""
        CREATE TRIGGER falha_indice BEFORE INSERT ON configuracoes
        WHEN NEW.chave='{service.INDEX_KEY}'
        BEGIN SELECT RAISE(ABORT, 'falha simulada no índice'); END
    """)
    connection.commit(); connection.close()
    content = b'<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00"/>'

    with pytest.raises(sqlite3.IntegrityError, match="falha simulada"):
        service.parse_response(response_xml(content=content))

    assert fiscal._get_setting(service.CONFIG_KEY) == ""
    assert fiscal._get_setting(service.INDEX_KEY) == ""
    assert list(tmp_path.glob("NSU_*.xml")) == []
