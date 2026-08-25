from __future__ import annotations

import pytest

from services.company_xml_import_service import CompanyXMLImportService


KEY = "1" * 44


def xml(*, status="100", model="55", emit_document="12345678000195", dest_document="98765432000198",
        omit_optional=False):
    optional = "" if omit_optional else "<xFant>LOJA TESTE</xFant><email>loja@example.com</email>"
    return f"""<?xml version='1.0' encoding='utf-8'?>
<nfeProc xmlns='http://www.portalfiscal.inf.br/nfe'>
 <NFe><infNFe Id='NFe{KEY}'><ide><mod>{model}</mod></ide>
  <emit><CNPJ>{emit_document}</CNPJ><xNome>FORNECEDOR LTDA</xNome>{optional}<IE>123</IE>
   <enderEmit><xLgr>RUA A</xLgr><nro>10</nro><xBairro>CENTRO</xBairro><cMun>2918407</cMun><xMun>JUAZEIRO</xMun><UF>BA</UF><CEP>48900000</CEP><fone>7430000000</fone></enderEmit></emit>
  <dest><CNPJ>{dest_document}</CNPJ><xNome>EMPRESA DESTINATARIA LTDA</xNome><IE>456</IE>
   <enderDest><xLgr>RUA B</xLgr><nro>20</nro><xBairro>SAO JOSE</xBairro><cMun>2927408</cMun><xMun>SALVADOR</xMun><UF>BA</UF><CEP>40000000</CEP></enderDest></dest>
 </infNFe></NFe><protNFe><infProt><chNFe>{KEY}</chNFe><cStat>{status}</cStat></infProt></protNFe>
</nfeProc>"""


def write(tmp_path, content, name="documento.xml"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_xml_valido_empresa_emitente_e_campos_comprovados(tmp_path):
    service = CompanyXMLImportService()
    review = service.inspect(write(tmp_path, xml()), known_documents=("12.345.678/0001-95",))
    assert review.selected_role == "emitente"
    selected = service.select(review, "emitente", known_documents=("12345678000195",)).selected
    assert selected.legal_name == "FORNECEDOR LTDA"
    assert selected.trade_name == "LOJA TESTE"
    assert selected.city_code == "2918407" and selected.email == "loja@example.com"


def test_xml_de_fornecedor_escolhe_empresa_destinataria(tmp_path):
    service = CompanyXMLImportService()
    review = service.inspect(write(tmp_path, xml()), known_documents=("98765432000198",))
    assert review.selected_role == "destinatário"
    assert service.select(review, review.selected_role, known_documents=("98765432000198",)).selected.legal_name == "EMPRESA DESTINATARIA LTDA"


def test_participante_ambiguo_exige_escolha(tmp_path):
    review = CompanyXMLImportService().inspect(write(tmp_path, xml()))
    assert review.selected_role == "" and {item.role for item in review.participants} == {"emitente", "destinatário"}


def test_campos_ausentes_permanecem_ausentes(tmp_path):
    review = CompanyXMLImportService().inspect(write(tmp_path, xml(omit_optional=True)))
    emit = next(item for item in review.participants if item.role == "emitente")
    assert emit.trade_name == "" and emit.email == ""


@pytest.mark.parametrize("content,message", [
    ("<quebrado>", "inválido ou adulterado"),
    (xml(status="101"), "não comprova autorização"),
    (xml(model="57"), "Modelo fiscal"),
    ("<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///x'>]><foo/>", "DTD ou entidades"),
])
def test_xml_invalido_adulterado_ou_nao_autorizado_e_rejeitado(tmp_path, content, message):
    with pytest.raises(ValueError, match=message):
        CompanyXMLImportService().inspect(write(tmp_path, content))


def test_incompatibilidade_de_cnpj_com_configuracao_licenca_ou_certificado(tmp_path):
    service = CompanyXMLImportService()
    review = service.inspect(write(tmp_path, xml()))
    with pytest.raises(ValueError, match="incompatível"):
        service.select(review, "emitente", known_documents=("11111111000191",))


def test_original_e_preservado_e_servico_nao_persiste_nem_transmite(tmp_path):
    path = write(tmp_path, xml())
    before = path.read_bytes()
    service = CompanyXMLImportService()
    review = service.inspect(path)
    service.select(review, "destinatário")
    assert path.read_bytes() == before
    assert set(vars(service)) == set()
