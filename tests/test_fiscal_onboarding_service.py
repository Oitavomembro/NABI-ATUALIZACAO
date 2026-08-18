from pathlib import Path

import pytest

from services.fiscal_onboarding_service import FiscalOnboardingService
from services.nfe_xml_service import NFeXMLService


def authorized_xml(*, crt="1", model="65", series="3", status="100") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
      <NFe><infNFe Id="NFe29260812345678000195650030000000011000000010">
        <ide><mod>{model}</mod><serie>{series}</serie><nNF>1</nNF><dhEmi>2026-08-18T10:00:00-03:00</dhEmi></ide>
        <emit><CNPJ>12345678000195</CNPJ><xNome>EMPRESA TESTE LTDA</xNome><xFant>EMPRESA TESTE</xFant>
          <enderEmit><xLgr>RUA A</xLgr><nro>10</nro><xBairro>CENTRO</xBairro><cMun>2927408</cMun><xMun>SALVADOR</xMun><UF>BA</UF><CEP>40000000</CEP></enderEmit>
          <IE>123456789</IE><CRT>{crt}</CRT>
        </emit>
        <det nItem="1"><prod><cProd>P1</cProd><xProd>PRODUTO</xProd><NCM>94036000</NCM><CFOP>5102</CFOP><uCom>UN</uCom><qCom>1</qCom><vUnCom>10.00</vUnCom><vProd>10.00</vProd></prod></det>
        <total><ICMSTot><vNF>10.00</vNF></ICMSTot></total>
      </infNFe></NFe>
      <protNFe><infProt><cStat>{status}</cStat></infProt></protNFe>
    </nfeProc>"""


def write_xml(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "documento.xml"
    path.write_text(content, encoding="utf-8")
    return path


def test_recupera_configuracao_de_xml_proprio_autorizado(tmp_path):
    draft = FiscalOnboardingService(NFeXMLService()).from_authorized_xml(
        write_xml(tmp_path, authorized_xml())
    )
    assert draft.cnpj == "12345678000195"
    assert draft.state == "BA"
    assert draft.tax_regime == "SIMPLES_NACIONAL"
    assert (draft.model, draft.series) == ("65", 3)
    assert draft.issuer["name"] == "EMPRESA TESTE LTDA"
    assert draft.issuer["city_code"] == "2927408"
    assert draft.issuer["zip_code"] == "40000000"
    assert draft.warnings == ()


def test_crt_3_exige_confirmacao_do_regime(tmp_path):
    draft = FiscalOnboardingService(NFeXMLService()).from_authorized_xml(
        write_xml(tmp_path, authorized_xml(crt="3", model="55", series="1"))
    )
    assert draft.tax_regime == ""
    assert "Lucro Presumido" in draft.warnings[0]


def test_rejeita_xml_sem_protocolo_de_autorizacao(tmp_path):
    with pytest.raises(ValueError, match="cStat 100"):
        FiscalOnboardingService(NFeXMLService()).from_authorized_xml(
            write_xml(tmp_path, authorized_xml(status="110"))
        )
