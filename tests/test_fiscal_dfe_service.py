import base64
import gzip
import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from lxml import etree

from services.fiscal_dfe_service import FiscalDFeService
from services.fiscal_service import FiscalResponse, FiscalService


@pytest.fixture
def dfe_service():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        database = root / "fiscal.db"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        connection.commit(); connection.close()
        fiscal = FiscalService(lambda: sqlite3.connect(database), storage_dir=root / "fiscal")
        yield FiscalDFeService(
            fiscal,
            storage_dir=root / "dfe",
            actor_provider=lambda: "admin",
            authorization_provider=lambda action: action == "transmit",
        ), fiscal, root


def test_monta_consulta_incremental_oficial_101(dfe_service):
    service, _fiscal, _root = dfe_service
    xml = service.build_request(
        cnpj="12.345.678/0001-95", state_code="29",
        environment="HOMOLOGACAO", last_nsu="123",
    )
    root = etree.fromstring(xml)
    assert root.get("versao") == "1.01"
    assert root.xpath("string(//*[local-name()='tpAmb'])") == "2"
    assert root.xpath("string(//*[local-name()='CNPJ'])") == "12345678000195"
    assert root.xpath("string(//*[local-name()='ultNSU'])") == "000000000000123"
    envelope = service._soap_envelope(xml)
    assert etree.fromstring(envelope).xpath(
        "count(//*[local-name()='nfeDistDFeInteresse']/*[local-name()='nfeDadosMsg']/*[local-name()='distDFeInt'])"
    ) == 1
    assert service.ENDPOINTS["HOMOLOGACAO"].startswith("https://hom1.nfe.fazenda.gov.br/")


def test_consulta_por_chave_exige_chave_valida(dfe_service):
    service, fiscal, _root = dfe_service
    key = fiscal.build_access_key(
        state_code="29", issued_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        cnpj="12345678000195", model="55", series=1, number=1,
        emission_type=1, numeric_code="12345678",
    )
    xml = service.build_request(
        cnpj="12345678000195", state_code="29", environment="PRODUCAO",
        access_key=key,
    )
    assert etree.fromstring(xml).xpath("string(//*[local-name()='chNFe'])") == key


def test_descompacta_persiste_e_avanca_nsu_atomicamente(dfe_service):
    service, _fiscal, _root = dfe_service
    content = b'<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00"><chNFe>1</chNFe></resNFe>'
    payload = base64.b64encode(gzip.compress(content)).decode("ascii")
    response = f'''<retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
      <tpAmb>2</tpAmb><cStat>138</cStat><xMotivo>Documento localizado</xMotivo>
      <ultNSU>200</ultNSU><maxNSU>250</maxNSU><loteDistDFeInt>
      <docZip NSU="200" schema="resNFe_v1.00.xsd">{payload}</docZip>
      </loteDistDFeInt></retDistDFeInt>'''
    result = service.parse_response(response)
    assert result.status_code == "138"
    assert result.last_nsu == "000000000000200"
    assert Path(result.documents[0]["path"]).read_bytes() == content
    assert service.state()["last_nsu"] == "000000000000200"
    listed = service.list_documents()
    assert listed[0]["nsu"] == "000000000000200"
    assert listed[0]["access_key"] == "1"


def test_resposta_sem_documento_tambem_preserva_nsu(dfe_service):
    service, _fiscal, _root = dfe_service
    result = service.parse_response(
        '<retDistDFeInt><cStat>137</cStat><xMotivo>Nenhum documento</xMotivo>'
        '<ultNSU>5</ultNSU><maxNSU>5</maxNSU></retDistDFeInt>'
    )
    assert result.documents == ()
    assert service.next_request(
        cnpj="12345678000195", state_code="29", environment="HOMOLOGACAO"
    ).find(b"000000000000005") > 0


def test_nao_regride_nsu_e_rejeita_documento_malformado(dfe_service):
    service, fiscal, _root = dfe_service
    fiscal._set_setting(service.CONFIG_KEY, '{"last_nsu":"100","max_nsu":"100"}')
    with pytest.raises(ValueError, match="regredir"):
        service.parse_response(
            '<retDistDFeInt><cStat>137</cStat><ultNSU>50</ultNSU><maxNSU>100</maxNSU></retDistDFeInt>'
        )
    assert service.state()["last_nsu"] == "000000000000100"
    invalid = base64.b64encode(b"nao-gzip").decode("ascii")
    with pytest.raises(ValueError, match="GZip inválido"):
        service.parse_response(
            f'<retDistDFeInt><cStat>138</cStat><docZip NSU="1" '
            f'schema="resNFe_v1.00.xsd">{invalid}</docZip></retDistDFeInt>'
        )


def test_schema_desconhecido_e_bloqueado(dfe_service):
    service, _fiscal, _root = dfe_service
    payload = base64.b64encode(gzip.compress(b"<xml/>" )).decode("ascii")
    with pytest.raises(ValueError, match="Schema DF-e não reconhecido"):
        service.parse_response(
            f'<retDistDFeInt><docZip NSU="1" schema="perigoso.xsd">{payload}</docZip></retDistDFeInt>'
        )


def test_monta_manifestacoes_oficiais_e_exige_justificativa(dfe_service):
    service, fiscal, _root = dfe_service
    key = fiscal.build_access_key(
        state_code="29", issued_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        cnpj="12345678000195", model="55", series=1, number=2,
        emission_type=1, numeric_code="87654321",
    )
    xml, identifier = service.build_manifestation(
        access_key=key, cnpj="12345678000195", environment="HOMOLOGACAO",
        kind="CONFIRMACAO",
    )
    root = etree.fromstring(xml)
    assert identifier == f"ID210200{key}01"
    assert root.xpath("string(//*[local-name()='tpEvento'])") == "210200"
    assert root.xpath("string(//*[local-name()='descEvento'])") == "Confirmacao da Operacao"
    with pytest.raises(ValueError, match="ao menos 15 caracteres"):
        service.build_manifestation(
            access_key=key, cnpj="12345678000195", environment="HOMOLOGACAO",
            kind="NAO_REALIZADA", justification="curta",
        )


def test_manifestacao_exige_documento_distribuido(dfe_service):
    service, fiscal, _root = dfe_service
    with patch.object(fiscal, "require_operational_readiness", return_value="admin"):
        with pytest.raises(ValueError, match="não foi localizada"):
            service.send_manifestation(
                access_key="1" * 44, kind="CIENCIA", password="senha"
            )


@pytest.mark.parametrize(
    ("actor_provider", "authorization_provider"),
    [
        (None, lambda _action: True),
        (lambda: "", lambda _action: True),
        (lambda: "admin", None),
        (lambda: "admin", lambda _action: False),
    ],
)
def test_manifestacao_falha_fechado_antes_de_ler_ou_transmitir(
    dfe_service, actor_provider, authorization_provider
):
    _service, fiscal, root = dfe_service
    service = FiscalDFeService(
        fiscal,
        storage_dir=root / "dfe-fail-closed",
        actor_provider=actor_provider,
        authorization_provider=authorization_provider,
    )
    with patch.object(service, "list_documents") as listed, patch.object(
        fiscal, "transmit"
    ) as transmitted:
        with pytest.raises(PermissionError):
            service.send_manifestation(
                access_key="1" * 44, kind="CIENCIA", password="senha"
            )
    listed.assert_not_called()
    transmitted.assert_not_called()


def test_manifestacao_nao_aceita_actor_livre(dfe_service):
    service, _fiscal, _root = dfe_service
    with pytest.raises(TypeError, match="actor"):
        service.send_manifestation(
            access_key="1" * 44,
            kind="CIENCIA",
            password="senha",
            actor="forjado",
        )


def test_manifestacao_assina_transmite_e_registra_sem_duplicar_conclusiva(dfe_service):
    service, fiscal, root = dfe_service
    key = fiscal.build_access_key(
        state_code="29", issued_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        cnpj="12345678000195", model="55", series=1, number=3,
        emission_type=1, numeric_code="11223344",
    )
    path = root / "dfe" / "NSU_000000000000001_resNFe_v1.00.xml"
    content = f"<resNFe><chNFe>{key}</chNFe></resNFe>".encode()
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    fiscal._set_setting(service.INDEX_KEY, json.dumps([{
        "nsu": "000000000000001", "schema": "resNFe_v1.00.xsd",
        "path": str(path), "sha256": hashlib.sha256(content).hexdigest(),
    }]))
    fiscal.save_config({
        "cnpj": "12345678000195", "environment": "HOMOLOGACAO",
        "certificate_path": "teste.pfx",
    })
    response = FiscalResponse(True, "135", "Evento registrado", "123")
    with patch.object(fiscal, "sign_xml", side_effect=lambda xml, **_kwargs: xml), patch.object(
        fiscal, "_event_envelope", side_effect=lambda xml: xml
    ), patch.object(fiscal, "transmit", return_value=response), patch.object(
        fiscal, "register_event", return_value={"success": True}
    ) as register, patch.object(
        fiscal, "require_operational_readiness", return_value="admin"
    ):
        sent, record = service.send_manifestation(
            access_key=key, kind="CONFIRMACAO", password="senha"
        )
    assert sent.success and record["success"]
    assert register.call_args.kwargs["event_type"] == "MANIFESTACAO_CONFIRMACAO"

    fiscal.list_events = lambda *_args: [{
        "success": True, "event_type": "MANIFESTACAO_CONFIRMACAO"
    }]
    with patch.object(fiscal, "require_operational_readiness", return_value="admin"):
        with pytest.raises(ValueError, match="manifestação conclusiva"):
            service.send_manifestation(
                access_key=key, kind="DESCONHECIMENTO", password="senha"
            )
