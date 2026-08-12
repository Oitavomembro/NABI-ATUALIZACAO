from __future__ import annotations

import base64
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from services.fiscal_service import FiscalResponse, FiscalService


class FiscalServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "fiscal.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        conn.commit(); conn.close()
        self.service = FiscalService(self.connect, storage_dir=Path(self.tmp.name) / "docs")
        self.password = "senha-fiscal"
        self.pfx_path = Path(self.tmp.name) / "certificado.pfx"
        self._create_pfx(self.pfx_path, self.password)

    def tearDown(self):
        self.tmp.cleanup()

    def connect(self):
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _create_pfx(path: Path, password: str):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA TESTE 12345678000195"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NabiCode Testes"),
        ])
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject).issuer_name(issuer).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=30))
            .sign(key, hashes.SHA256())
        )
        path.write_bytes(pkcs12.serialize_key_and_certificates(
            b"nabicode", key, cert, None,
            serialization.BestAvailableEncryption(password.encode("utf-8")),
        ))

    def test_modulo_desabilitado_nao_bloqueia_sistema(self):
        self.assertFalse(self.service.is_enabled())
        self.assertIn("não está habilitado", self.service.validate_ready(operation="autorizacao")[0])

    def test_requests_ausente_nao_impede_inicializacao_do_sistema(self):
        with patch("services.fiscal_service.requests", None):
            service = FiscalService(self.connect, storage_dir=Path(self.tmp.name) / "sem_requests")
            self.assertFalse(service.is_enabled())
            service.save_config({
                "environment": "HOMOLOGACAO",
                "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid/autorizacao"}},
            })
            with self.assertRaisesRegex(RuntimeError, "ATUALIZAR_DEPENDENCIAS"):
                service.transmit(
                    operation="autorizacao", xml=b"<xml/>",
                    pfx_path=self.pfx_path, password=self.password,
                )

    def test_configuracao_e_certificado_opcionais(self):
        config = self.service.save_config({
            "enabled": True, "environment": "HOMOLOGACAO", "cnpj": "12.345.678/0001-95",
            "state": "BA", "tax_regime": "SIMPLES",
            "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid/autorizacao"}},
        })
        self.assertEqual(config["cnpj"], "12345678000195")
        info = self.service.configure_certificate(self.pfx_path, self.password)
        self.assertFalse(info.expired)
        self.assertEqual(info.document, "12345678000195")
        self.assertEqual(self.service.validate_ready(operation="autorizacao"), [])

    def test_configuracao_preserva_dados_do_emitente_e_serie_devolucao(self):
        config = self.service.save_config({
            "issuer": {
                "name": "EMPRESA TESTE", "state_registration": "123.456.789",
                "city_code": "2927408", "city": "SALVADOR", "street": "RUA A",
                "number": "10", "district": "CENTRO", "zip_code": "40000-000",
                "return_series": "7",
            }
        })
        issuer = config["issuer"]
        self.assertEqual(issuer["state_registration"], "123456789")
        self.assertEqual(issuer["city_code"], "2927408")
        self.assertEqual(issuer["zip_code"], "40000000")
        self.assertEqual(issuer["return_series"], 7)
        self.assertEqual(self.service.load_config()["issuer"]["name"], "EMPRESA TESTE")

    def test_regras_fiscais_bloqueiam_ncm_e_cfop_invalidos(self):
        issuer = {
            "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
            "city": "SALVADOR", "state": "BA", "street": "RUA TESTE", "number": "10",
            "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
            "tax_regime_code": 1,
        }
        problems = self.service.validate_document_rules(
            issuer=issuer, recipient={},
            items=[{"code":"P1","description":"Produto","quantity":1,"unit_price":10,"ncm":"00000000","cfop":"1102","unit":"UN"}],
            document={"model":"55","state_code":"29","operation_type":1},
        )
        self.assertTrue(any("NCM" in item for item in problems))
        self.assertTrue(any("CFOP de saída" in item for item in problems))

    def test_nfce_exige_consumidor_final_e_operacao_de_saida(self):
        issuer = {
            "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
            "state": "BA", "state_registration": "123", "tax_regime_code": 1,
        }
        problems = self.service.validate_document_rules(
            issuer=issuer, recipient={},
            items=[{"code":"P1","description":"Produto","quantity":1,"unit_price":10,"ncm":"94036000","cfop":"1102","unit":"UN"}],
            document={"model":"65","state_code":"29","operation_type":0,"final_consumer":0,"presence":0},
        )
        self.assertTrue(any("consumidor final" in item for item in problems))
        self.assertTrue(any("operação de saída" in item for item in problems))

    def test_regime_normal_gera_icms00_e_total_icms(self):
        issued = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
        xml, _key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA NORMAL", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA TESTE", "number": "10",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 3,
            },
            recipient={"document": "12345678901", "name": "CLIENTE TESTE"},
            items=[{
                "code": "P1", "description": "produto tributado", "quantity": 2, "unit_price": 10,
                "ncm": "94036000", "cfop": "5102", "unit": "UN", "cst": "00", "icms_rate": "18.00",
            }],
            document={"model": "55", "series": 1, "number": 13, "state_code": "29", "issued_at": issued, "environment": "HOMOLOGACAO", "numeric_code": "12345679"},
        )
        root = etree.fromstring(xml)
        self.assertEqual(root.xpath("string(//*[local-name()='ICMS00']/*[local-name()='vBC'])"), "20.00")
        self.assertEqual(root.xpath("string(//*[local-name()='ICMS00']/*[local-name()='vICMS'])"), "3.60")
        self.assertEqual(root.xpath("string(//*[local-name()='ICMSTot']/*[local-name()='vICMS'])"), "3.60")

    def test_assinatura_xml_dsig(self):
        signed = self.service.sign_xml(
            '<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe123"><ide/></infNFe></NFe>',
            reference_id="NFe123", pfx_path=self.pfx_path, password=self.password,
        )
        root = etree.fromstring(signed)
        signature = root.xpath("//*[local-name()='Signature']")
        self.assertEqual(len(signature), 1)
        self.assertEqual(root.xpath("string(//*[local-name()='Reference']/@URI)"), "#NFe123")
        self.assertTrue(root.xpath("string(//*[local-name()='SignatureValue'])"))

    def test_resposta_so_autoriza_com_protocolo(self):
        without_protocol = self.service.parse_response("<ret><cStat>100</cStat><xMotivo>Autorizado</xMotivo></ret>")
        self.assertFalse(without_protocol.success)
        authorized = self.service.parse_response("<ret><cStat>100</cStat><xMotivo>Autorizado</xMotivo><nProt>12345</nProt></ret>")
        self.assertTrue(authorized.success)
        self.assertEqual(authorized.protocol, "12345")

    def test_armazenamento_separa_ambiente_e_modelo(self):
        key = "1" * 44
        request_xml = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00"/></NFe>'
        response_xml = f'<ret><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe><nProt>12345</nProt></infProt></protNFe></ret>'
        response = FiscalResponse(True, "100", "Autorizado", "12345", raw_xml=response_xml, access_key=key)
        record = self.service.store_document(
            access_key=key, model="55", environment="HOMOLOGACAO",
            request_xml=request_xml, response=response, actor="admin",
        )
        self.assertEqual(record["status"], "AUTORIZADO")
        self.assertTrue(Path(record["request_path"]).is_file())
        self.assertEqual(len(self.service.list_documents()), 1)


    def test_gera_chave_e_rascunho_xml_nfe(self):
        issued = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
        xml, key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA TESTE", "number": "10",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={"document": "12345678901", "name": "CLIENTE TESTE"},
            items=[{"code": "P1", "description": "produto teste", "quantity": 2, "unit_price": 10, "ncm": "94036000", "cfop": "5102", "unit": "UN"}],
            document={"model": "55", "series": 1, "number": 12, "state_code": "29", "issued_at": issued, "environment": "HOMOLOGACAO", "numeric_code": "12345678"},
        )
        self.assertEqual(len(key), 44)
        root = etree.fromstring(xml)
        self.assertEqual(root.xpath("string(//*[local-name()='infNFe']/@Id)"), f"NFe{key}")
        self.assertEqual(root.xpath("string(//*[local-name()='xProd'])"), "PRODUTO TESTE")
        self.assertEqual(root.xpath("string(//*[local-name()='vNF'])"), "20.00")

    def test_eventos_consulta_e_inutilizacao(self):
        key = "1" * 44
        cancel_xml, cancel_id = self.service.build_event_xml(
            event_type="CANCELAMENTO", access_key=key, sequence=1,
            actor_document="12345678000195", protocol="123456",
            justification="Cancelamento solicitado pelo cliente final.",
        )
        self.assertTrue(cancel_id.startswith("ID110111"))
        self.assertEqual(etree.fromstring(cancel_xml).xpath("string(//*[local-name()='nProt'])"), "123456")
        cce_xml, _ = self.service.build_event_xml(
            event_type="CCE", access_key=key, sequence=2, actor_document="12345678000195",
            correction="Corrigir a descrição complementar do produto.",
        )
        self.assertEqual(etree.fromstring(cce_xml).xpath("string(//*[local-name()='tpEvento'])"), "110110")
        inut_xml, inut_id = self.service.build_inutilization_xml(
            state_code="29", year=2026, cnpj="12345678000195", model="55", series=1,
            start_number=10, end_number=12, justification="Faixa não utilizada por erro operacional.",
        )
        self.assertTrue(inut_id.startswith("ID2926"))
        self.assertEqual(etree.fromstring(inut_xml).xpath("string(//*[local-name()='nNFFin'])"), "12")
        query = etree.fromstring(self.service.build_query_xml(access_key=key))
        self.assertEqual(query.xpath("string(//*[local-name()='xServ'])"), "CONSULTAR")

    def test_registra_evento_e_gera_danfe_apenas_autorizada(self):
        key = "2" * 44
        response = FiscalResponse(True, "135", "Evento registrado", "EV123", raw_xml="<ret><cStat>135</cStat><nProt>EV123</nProt></ret>")
        record = self.service.register_event(access_key=key, event_type="CCE", response=response, request_xml="<evento/>", actor="admin")
        self.assertTrue(Path(record["request_path"]).is_file())
        self.assertEqual(len(self.service.list_events(key)), 1)
        proc = (
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe' + key + '">'
            '<ide><mod>55</mod><serie>1</serie><nNF>10</nNF></ide><emit><CNPJ>12345678000195</CNPJ>'
            '<xNome>EMPRESA TESTE</xNome></emit><dest><xNome>CLIENTE</xNome></dest><det nItem="1"><prod>'
            '<cProd>P1</cProd><xProd>PRODUTO</xProd><qCom>1.0000</qCom><uCom>UN</uCom>'
            '<vUnCom>10.00</vUnCom><vProd>10.00</vProd></prod></det><total><ICMSTot><vNF>10.00</vNF>'
            '</ICMSTot></total></infNFe></NFe><protNFe><infProt><cStat>100</cStat><chNFe>' + key +
            '</chNFe><nProt>12345</nProt></infProt></protNFe></nfeProc>'
        )
        pdf = self.service.generate_danfe_pdf(authorized_xml=proc, output_path=Path(self.tmp.name) / "danfe.pdf")
        self.assertTrue(pdf.is_file())
        self.assertGreater(pdf.stat().st_size, 500)
        with self.assertRaises(ValueError):
            self.service.generate_danfe_pdf(authorized_xml="<NFe/>", output_path=Path(self.tmp.name) / "invalido.pdf")


    def test_fluxos_assinados_de_autorizacao_consulta_evento_e_inutilizacao(self):
        self.service.save_config({
            "enabled": True, "environment": "HOMOLOGACAO", "cnpj": "12345678000195", "state": "BA",
            "tax_regime": "SIMPLES", "certificate_path": str(self.pfx_path),
            "endpoints": {"HOMOLOGACAO": {
                "autorizacao": "https://sefaz.invalid/aut", "consulta": "https://sefaz.invalid/con",
                "evento": "https://sefaz.invalid/eve", "inutilizacao": "https://sefaz.invalid/inu",
            }},
        })
        xml, key = self.service.build_document_xml(
            issuer={"cnpj":"12345678000195","name":"EMPRESA","city_code":"2925105","city":"SALVADOR","state":"BA","street":"RUA","number":"1","district":"CENTRO","zip_code":"40000000","state_registration":"123","tax_regime_code":1},
            recipient={"document":"12345678901","name":"CLIENTE"},
            items=[{"code":"P1","description":"PRODUTO","quantity":1,"unit_price":10,"ncm":"94036000","cfop":"5102","unit":"UN"}],
            document={"model":"55","series":1,"number":1,"state_code":"29","environment":"HOMOLOGACAO","numeric_code":"87654321"},
        )
        original_transmit = self.service.transmit
        calls = []
        def fake_transmit(**kwargs):
            calls.append(kwargs["operation"])
            if kwargs["operation"] == "autorizacao":
                raw = f'<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe><nProt>12345</nProt></infProt></protNFe></retEnviNFe>'
                return FiscalResponse(True, "100", "Autorizado", "12345", raw_xml=raw)
            if kwargs["operation"] == "consulta":
                return FiscalResponse(True, "100", "Autorizado", "12345", raw_xml="<ret><cStat>100</cStat><nProt>12345</nProt></ret>")
            return FiscalResponse(True, "135", "Evento registrado", "EV123", raw_xml="<ret><cStat>135</cStat><nProt>EV123</nProt></ret>")
        self.service.transmit = fake_transmit
        try:
            response, record = self.service.authorize_document(xml=xml, access_key=key, password=self.password, actor="admin")
            self.assertTrue(response.success)
            self.assertTrue(Path(record["processed_path"]).is_file())
            self.assertTrue(self.service.consult_document(access_key=key, password=self.password).success)
            event_response, _ = self.service.send_event(event_type="CCE", access_key=key, sequence=1, password=self.password, actor="admin", correction="Corrigir descrição complementar do produto.")
            self.assertTrue(event_response.success)
            inut_response, _ = self.service.inutilize_numbers(year=2026, model="55", series=1, start_number=20, end_number=21, justification="Faixa não utilizada por falha operacional.", password=self.password, actor="admin")
            self.assertTrue(inut_response.success)
        finally:
            self.service.transmit = original_transmit
        self.assertEqual(calls, ["autorizacao", "consulta", "evento", "inutilizacao"])

    def test_contingencia_exige_justificativa_e_recalcula_chave(self):
        xml, original_key = self.service.build_document_xml(
            issuer={"cnpj":"12345678000195","name":"EMPRESA","city_code":"2925105","city":"SALVADOR","state":"BA","street":"RUA","number":"1","district":"CENTRO","zip_code":"40000000","state_registration":"123","tax_regime_code":1},
            recipient={"document":"12345678901","name":"CLIENTE"},
            items=[{"code":"P1","description":"PRODUTO","quantity":1,"unit_price":10,"ncm":"94036000","cfop":"5102","unit":"UN"}],
            document={"model":"55","series":1,"number":1,"state_code":"29","environment":"HOMOLOGACAO","numeric_code":"87654321"},
        )
        result = etree.fromstring(self.service.apply_contingency(xml, reason="Indisponibilidade temporária da SEFAZ.", emission_type=9))
        contingency_key = str(result.xpath("string(//*[local-name()='infNFe']/@Id)")).replace("NFe", "")
        self.assertEqual(result.xpath("string(//*[local-name()='tpEmis'])"), "9")
        self.assertTrue(result.xpath("string(//*[local-name()='dhCont'])"))
        self.assertIn("Indisponibilidade", result.xpath("string(//*[local-name()='xJust'])"))
        self.assertEqual(len(contingency_key), 44)
        self.assertNotEqual(contingency_key, original_key)
        self.assertEqual(contingency_key[34], "9")
        self.assertEqual(result.xpath("string(//*[local-name()='cDV'])"), contingency_key[-1])
        self.assertEqual(self.service.calculate_access_key_digit(contingency_key[:43]), contingency_key[-1])
        with self.assertRaises(ValueError):
            self.service.apply_contingency(xml, reason="curta", emission_type=9)

    def test_contingencia_bloqueia_xml_sem_dados_para_nova_chave(self):
        xml = '<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1"><ide><tpEmis>1</tpEmis></ide></infNFe></NFe>'
        with self.assertRaisesRegex(ValueError, "Data de emissão|Dados insuficientes"):
            self.service.apply_contingency(xml, reason="Indisponibilidade temporária da SEFAZ.", emission_type=9)


    def test_perfil_fiscal_valida_uf_regime_municipio_e_ie(self):
        problems = self.service.validate_fiscal_profile(
            issuer={"cnpj": "123", "state": "XX", "tax_regime_code": 9, "city_code": "1", "state_registration": ""},
            model="55",
        )
        self.assertGreaterEqual(len(problems), 5)
        self.assertEqual(self.service.validate_fiscal_profile(
            issuer={
                "cnpj": "12345678000195", "state": "BA", "tax_regime_code": 1,
                "city_code": "2927408", "state_registration": "123456",
            },
            model="55",
        ), [])

    def test_configuracao_rejeita_uf_e_regime_invalidos(self):
        with self.assertRaises(ValueError):
            self.service.save_config({"state": "XX"})
        with self.assertRaises(ValueError):
            self.service.save_config({"tax_regime": "INVENTADO"})

    def test_evento_aceito_nao_autoriza_documento_e_rejeicao_fica_auditada(self):
        event_response = self.service.parse_response(
            "<ret><cStat>135</cStat><xMotivo>Evento registrado</xMotivo><nProt>EV1</nProt></ret>"
        )
        self.assertTrue(event_response.success)
        record = self.service.store_document(
            access_key="3" * 44, model="55", environment="HOMOLOGACAO",
            request_xml="<NFe/>", response=event_response, actor="admin",
        )
        self.assertEqual(record["status"], "REJEITADO")
        rejections = self.service.list_rejections(operation="AUTORIZACAO", access_key="3" * 44)
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["status_code"], "135")

    def test_validacao_xsd_externo(self):
        xsd = Path(self.tmp.name) / "simple.xsd"
        xsd.write_text(
            """<?xml version='1.0' encoding='utf-8'?>
            <xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'>
              <xs:element name='doc'>
                <xs:complexType><xs:sequence><xs:element name='valor' type='xs:integer'/></xs:sequence></xs:complexType>
              </xs:element>
            </xs:schema>""",
            encoding="utf-8",
        )
        self.assertEqual(self.service.validate_xml_schema("<doc><valor>10</valor></doc>", xsd), [])
        errors = self.service.validate_xml_schema("<doc><valor>abc</valor></doc>", xsd)
        self.assertTrue(errors)


    def test_resposta_aninhada_prioriza_status_do_documento_e_evento(self):
        authorization = self.service.parse_response(
            """<retEnviNFe xmlns='http://www.portalfiscal.inf.br/nfe'>
            <cStat>104</cStat><xMotivo>Lote processado</xMotivo>
            <protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>
            <nProt>123456789</nProt></infProt></protNFe></retEnviNFe>"""
        )
        self.assertTrue(authorization.success)
        self.assertEqual(authorization.status_code, "100")
        self.assertEqual(authorization.protocol, "123456789")

        event = self.service.parse_response(
            """<retEnvEvento xmlns='http://www.portalfiscal.inf.br/nfe'>
            <cStat>128</cStat><xMotivo>Lote processado</xMotivo>
            <retEvento><infEvento><cStat>135</cStat><xMotivo>Evento registrado</xMotivo>
            <nProt>EV123</nProt></infEvento></retEvento></retEnvEvento>"""
        )
        self.assertTrue(event.success)
        self.assertEqual(event.status_code, "135")
        self.assertEqual(event.protocol, "EV123")

    def test_lote_processado_sem_evento_aceito_nao_e_sucesso(self):
        response = self.service.parse_response(
            "<retEnvEvento><cStat>128</cStat><xMotivo>Lote processado</xMotivo></retEnvEvento>"
        )
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, "128")

    def test_evento_rejeitado_e_registrado_na_auditoria(self):
        key = "4" * 44
        response = self.service.parse_response(
            """<retEnvEvento><cStat>128</cStat><retEvento><infEvento>
            <cStat>573</cStat><xMotivo>Duplicidade de evento</xMotivo>
            </infEvento></retEvento></retEnvEvento>"""
        )
        record = self.service.register_event(
            access_key=key, event_type="CCE", response=response,
            request_xml="<evento/>", actor="admin",
        )
        self.assertFalse(record["success"])
        rejected = self.service.list_rejections(operation="CCE", access_key=key)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["status_code"], "573")

    def test_resposta_autorizada_de_outra_chave_e_bloqueada(self):
        requested = "5" * 44
        returned = "6" * 44
        response = self.service.parse_response(
            f"<ret><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo>"
            f"<chNFe>{returned}</chNFe><nProt>123</nProt></infProt></protNFe></ret>"
        )
        self.assertTrue(response.success)
        self.assertEqual(response.access_key, returned)
        with self.assertRaises(ValueError):
            self.service.store_document(
                access_key=requested, model="55", environment="HOMOLOGACAO",
                request_xml=f"<NFe><infNFe Id='NFe{requested}'/></NFe>",
                response=response, actor="admin",
            )

    def test_merge_protocolo_rejeita_chave_diferente(self):
        requested = "7" * 44
        returned = "8" * 44
        request_xml = f"<NFe xmlns='http://www.portalfiscal.inf.br/nfe'><infNFe Id='NFe{requested}'/></NFe>"
        response_xml = (
            f"<ret xmlns='http://www.portalfiscal.inf.br/nfe'><protNFe><infProt>"
            f"<cStat>100</cStat><chNFe>{returned}</chNFe><nProt>123</nProt>"
            f"</infProt></protNFe></ret>"
        )
        with self.assertRaises(ValueError):
            self.service.merge_authorization_protocol(request_xml, response_xml)

    def test_reserva_confirma_e_bloqueia_reuso_de_numeracao(self):
        reservation = self.service.reserve_number(model="55", series=1, actor="admin", environment="HOMOLOGACAO")
        self.assertEqual(reservation["number"], 1)
        key = self.service.build_access_key(
            state_code="29", issued_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            cnpj="12345678000195", model="55", series=1, number=1, numeric_code="12345678",
        )
        confirmed = self.service.confirm_number(reservation["id"], access_key=key, actor="admin")
        self.assertEqual(confirmed["status"], "CONFIRMADO")
        self.assertEqual(confirmed["access_key"], key)
        with self.assertRaises(ValueError):
            self.service.release_number(reservation["id"], actor="admin", reason="Tentativa inválida")
        next_reservation = self.service.reserve_number(model="55", series=1, actor="admin", environment="HOMOLOGACAO")
        self.assertEqual(next_reservation["number"], 2)

    def test_confirmacao_rejeita_chave_de_outra_numeracao(self):
        reservation = self.service.reserve_number(model="65", series=3, actor="caixa", environment="HOMOLOGACAO")
        wrong_key = self.service.build_access_key(
            state_code="29", issued_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            cnpj="12345678000195", model="65", series=3, number=99, numeric_code="87654321",
        )
        with self.assertRaises(ValueError):
            self.service.confirm_number(reservation["id"], access_key=wrong_key, actor="caixa")
        current = self.service.numbering_status(model="65", series=3)[0]
        self.assertEqual(current["status"], "RESERVADO")

    def test_reserva_expirada_e_recuperada_sem_reutilizar_numero(self):
        reservation = self.service.reserve_number(model="55", series=9, actor="admin", ttl_minutes=1)
        conn = self.connect()
        row = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (FiscalService.NUMBERING_KEY,)).fetchone()
        data = __import__("json").loads(row[0])
        data["records"][reservation["id"]]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        conn.execute("UPDATE configuracoes SET valor = ? WHERE chave = ?", (__import__("json").dumps(data), FiscalService.NUMBERING_KEY))
        conn.commit(); conn.close()
        second = self.service.reserve_number(model="55", series=9, actor="admin")
        self.assertEqual(second["number"], 2)
        records = {row["number"]: row for row in self.service.numbering_status(model="55", series=9)}
        self.assertEqual(records[1]["status"], "LIBERADO")
        self.assertEqual(records[2]["status"], "RESERVADO")

    def test_fila_transmissao_conclui_item_com_sucesso(self):
        self.service.save_config({
            "enabled": True,
            "environment": "HOMOLOGACAO",
            "cnpj": "12345678000195",
            "state": "BA",
            "tax_regime": "SIMPLES",
            "certificate_path": str(self.pfx_path),
            "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid"}, "PRODUCAO": {}},
        })
        key = "1" * 44
        xml = f'<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}" versao="4.00"/></NFe></enviNFe>'
        item = self.service.enqueue_transmission(operation="autorizacao", xml=xml, actor="admin")
        response_xml = f'<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe><nProt>123</nProt></infProt></protNFe></retEnviNFe>'
        original = self.service.transmit
        self.service.transmit = lambda **kwargs: FiscalResponse(True, "100", "Autorizado", protocol="123", access_key=key, raw_xml=response_xml)
        try:
            processed = self.service.process_transmission_queue(password=self.password)
        finally:
            self.service.transmit = original
        self.assertEqual(processed[0]["id"], item["id"])
        self.assertEqual(processed[0]["status"], "CONCLUIDO")
        self.assertEqual(self.service.list_transmission_queue(status="CONCLUIDO")[0]["last_status_code"], "100")

    def test_fila_transmissao_reagenda_e_falha_apos_limite(self):
        self.service.save_config({
            "enabled": True,
            "environment": "HOMOLOGACAO",
            "cnpj": "12345678000195",
            "state": "BA",
            "tax_regime": "SIMPLES",
            "certificate_path": str(self.pfx_path),
            "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid"}, "PRODUCAO": {}},
        })
        key = "2" * 44
        xml = f'<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}" versao="4.00"/></NFe></enviNFe>'
        item = self.service.enqueue_transmission(
            operation="autorizacao", xml=xml, actor="admin", max_attempts=2, retry_minutes=1
        )
        original = self.service.transmit
        self.service.transmit = lambda **kwargs: (_ for _ in ()).throw(TimeoutError("timeout"))
        try:
            first = self.service.process_transmission_queue(password=self.password)[0]
            self.assertEqual(first["status"], "ERRO")
            later = datetime.fromisoformat(first["next_attempt_at"]) + timedelta(seconds=1)
            second = self.service.process_transmission_queue(password=self.password, now=later)[0]
        finally:
            self.service.transmit = original
        self.assertEqual(second["id"], item["id"])
        self.assertEqual(second["status"], "FALHA")
        self.assertEqual(second["attempts"], 2)

    def test_fila_autorizacao_rejeita_xml_sem_chave(self):
        with self.assertRaisesRegex(ValueError, "chave de acesso"):
            self.service.enqueue_transmission(operation="autorizacao", xml="<enviNFe/>", actor="admin")

    def test_fila_autorizacao_bloqueia_resposta_de_outra_chave(self):
        self.service.save_config({
            "enabled": True,
            "environment": "HOMOLOGACAO",
            "cnpj": "12345678000195",
            "state": "BA",
            "tax_regime": "SIMPLES",
            "certificate_path": str(self.pfx_path),
            "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid"}, "PRODUCAO": {}},
        })
        key = "3" * 44
        other_key = "4" * 44
        xml = f'<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}" versao="4.00"/></NFe></enviNFe>'
        item = self.service.enqueue_transmission(operation="autorizacao", xml=xml, actor="admin", max_attempts=1)
        original = self.service.transmit
        self.service.transmit = lambda **kwargs: FiscalResponse(True, "100", "Autorizado", protocol="999", access_key=other_key, raw_xml="<ret/>")
        try:
            processed = self.service.process_transmission_queue(password=self.password)
        finally:
            self.service.transmit = original
        self.assertEqual(processed[0]["id"], item["id"])
        self.assertEqual(processed[0]["status"], "FALHA")
        self.assertIn("não corresponde", processed[0]["last_error"])

    def test_fila_autorizacao_consulta_recibo_ate_resposta_definitiva(self):
        self.service.save_config({
            "enabled": True,
            "environment": "HOMOLOGACAO",
            "cnpj": "12345678000195",
            "state": "BA",
            "tax_regime": "SIMPLES",
            "certificate_path": str(self.pfx_path),
            "endpoints": {
                "HOMOLOGACAO": {
                    "autorizacao": "https://sefaz.invalid/aut",
                    "recibo": "https://sefaz.invalid/rec",
                },
                "PRODUCAO": {},
            },
        })
        key = "5" * 44
        original_xml = f'<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}" versao="4.00"/></NFe></enviNFe>'
        item = self.service.enqueue_transmission(
            operation="autorizacao", xml=original_xml, actor="admin", retry_minutes=1
        )
        calls = []
        response_xml = (
            f'<retConsReciNFe xmlns="http://www.portalfiscal.inf.br/nfe"><cStat>104</cStat>'
            f'<protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo>'
            f'<chNFe>{key}</chNFe><nProt>123456789</nProt></infProt></protNFe></retConsReciNFe>'
        )
        def fake_transmit(**kwargs):
            calls.append((kwargs["operation"], kwargs["xml"]))
            if kwargs["operation"] == "autorizacao":
                return FiscalResponse(False, "103", "Lote recebido", receipt="987654321", raw_xml="<ret><cStat>103</cStat><nRec>987654321</nRec></ret>")
            return FiscalResponse(True, "100", "Autorizado", protocol="123456789", access_key=key, raw_xml=response_xml)
        original = self.service.transmit
        self.service.transmit = fake_transmit
        try:
            first = self.service.process_transmission_queue(password=self.password)[0]
            self.assertEqual(first["status"], "PENDENTE")
            self.assertEqual(first["operation"], "recibo")
            self.assertEqual(first["receipt"], "987654321")
            query_xml = base64.b64decode(first["xml_b64"])
            self.assertIn(b"consReciNFe", query_xml)
            self.assertIn(b"987654321", query_xml)
            later = datetime.fromisoformat(first["next_attempt_at"]) + timedelta(seconds=1)
            second = self.service.process_transmission_queue(password=self.password, now=later)[0]
        finally:
            self.service.transmit = original
        self.assertEqual(second["id"], item["id"])
        self.assertEqual(second["status"], "CONCLUIDO")
        self.assertEqual(second["document_record"]["protocol"], "123456789")
        self.assertEqual([operation for operation, _ in calls], ["autorizacao", "recibo"])

    def test_fila_recibo_em_processamento_permanece_pendente(self):
        self.service.save_config({
            "enabled": True, "environment": "HOMOLOGACAO",
            "cnpj": "12345678000195", "state": "BA", "tax_regime": "SIMPLES",
            "certificate_path": str(self.pfx_path),
            "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid/aut", "recibo": "https://sefaz.invalid/rec"}, "PRODUCAO": {}},
        })
        key = "6" * 44
        xml = f'<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}" versao="4.00"/></NFe></enviNFe>'
        self.service.enqueue_transmission(operation="autorizacao", xml=xml, actor="admin", retry_minutes=1)
        responses = iter([
            FiscalResponse(False, "103", "Lote recebido", receipt="123", raw_xml="<ret/>"),
            FiscalResponse(False, "105", "Lote em processamento", receipt="123", raw_xml="<ret/>")
        ])
        original = self.service.transmit
        self.service.transmit = lambda **_: next(responses)
        try:
            first = self.service.process_transmission_queue(password=self.password)[0]
            later = datetime.fromisoformat(first["next_attempt_at"]) + timedelta(seconds=1)
            second = self.service.process_transmission_queue(password=self.password, now=later)[0]
        finally:
            self.service.transmit = original
        self.assertEqual(second["status"], "PENDENTE")
        self.assertEqual(second["operation"], "recibo")
        self.assertEqual(second["last_status_code"], "105")
        self.assertEqual(second["attempts"], 2)

    def test_reenvio_manual_reabre_item_falhado(self):
        item = self.service.enqueue_transmission(
            operation="consulta", xml="<consSitNFe/>", actor="admin", max_attempts=1
        )
        original = self.service.transmit
        self.service.transmit = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("indisponível"))
        try:
            failed = self.service.process_transmission_queue(password=self.password)[0]
        finally:
            self.service.transmit = original
        self.assertEqual(failed["status"], "FALHA")
        reopened = self.service.retry_transmission(item["id"], actor="gerente")
        self.assertEqual(reopened["status"], "PENDENTE")
        self.assertEqual(reopened["retried_by"], "gerente")



    def _authorized_signed_xml(self):
        key = self.service.build_access_key(
            state_code="29", issued_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            cnpj="12345678000195", model="55", series=1, number=321,
            emission_type=1, numeric_code="12345678",
        )
        unsigned = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00"><ide><mod>55</mod></ide></infNFe></NFe>'
        signed = self.service.sign_xml(
            unsigned, reference_id=f"NFe{key}", pfx_path=self.pfx_path, password=self.password,
        )
        response = f'<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe><nProt>123456789012345</nProt></infProt></protNFe></retEnviNFe>'
        return key, self.service.merge_authorization_protocol(signed, response)

    def test_xml_autorizado_importado_valida_assinatura_chave_e_protocolo(self):
        key, processed = self._authorized_signed_xml()
        validation = self.service.validate_authorized_xml(processed)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["access_key"], key)
        self.assertTrue(validation["signature"]["valid"])
        record = self.service.import_authorized_xml(processed, actor="admin")
        self.assertEqual(record["source"], "IMPORTADO")
        self.assertTrue(Path(record["processed_path"]).is_file())
        self.assertEqual(len(record["processed_sha256"]), 64)

    def test_xml_autorizado_adulterado_e_bloqueado(self):
        _key, processed = self._authorized_signed_xml()
        root = etree.fromstring(processed)
        inf = root.xpath("//*[local-name()='infNFe']")[0]
        etree.SubElement(inf, "adulterado").text = "1"
        adulterado = etree.tostring(root, xml_declaration=True, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Digest"):
            self.service.validate_authorized_xml(adulterado)

    def test_xml_autorizado_com_protocolo_de_outra_chave_e_bloqueado(self):
        _key, processed = self._authorized_signed_xml()
        root = etree.fromstring(processed)
        protocol_key = root.xpath("//*[local-name()='chNFe']")[0]
        protocol_key.text = ("9" * 43) + "0"
        with self.assertRaisesRegex(ValueError, "outra chave"):
            self.service.validate_authorized_xml(etree.tostring(root))


if __name__ == "__main__":
    unittest.main()

    def test_transmissao_restringe_e_remove_pems_temporarios(self):
        observed = {}

        class Response:
            content = b"<retEnviNFe><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><nProt>123</nProt><chNFe>29260812345678000195550010000000011000000010</chNFe></infProt></protNFe></retEnviNFe>"
            def raise_for_status(self):
                return None

        def fake_post(_url, **kwargs):
            cert_path, key_path = map(Path, kwargs["cert"])
            observed["paths"] = (cert_path, key_path)
            observed["modes"] = (cert_path.stat().st_mode & 0o777, key_path.stat().st_mode & 0o777)
            self.assertTrue(cert_path.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----"))
            self.assertTrue(key_path.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----"))
            return Response()

        self.service.http_post = fake_post
        self.service.save_config({
            "enabled": True, "environment": "HOMOLOGACAO",
            "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid/autorizacao"}},
        })
        response = self.service.transmit(
            operation="autorizacao", xml=b"<xml/>",
            pfx_path=self.pfx_path, password=self.password,
        )
        self.assertTrue(response.success)
        self.assertEqual(observed["modes"], (0o600, 0o600))
        self.assertTrue(all(not path.exists() for path in observed["paths"]))

    def test_transmissao_remove_pems_quando_http_falha(self):
        observed = {}

        def fake_post(_url, **kwargs):
            observed["paths"] = tuple(map(Path, kwargs["cert"]))
            raise RuntimeError("falha simulada")

        self.service.http_post = fake_post
        self.service.save_config({
            "enabled": True, "environment": "HOMOLOGACAO",
            "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid/autorizacao"}},
        })
        with self.assertRaises(RuntimeError):
            self.service.transmit(
                operation="autorizacao", xml=b"<xml/>",
                pfx_path=self.pfx_path, password=self.password,
            )
        self.assertTrue(all(not path.exists() for path in observed["paths"]))


class FiscalDocumentIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "fiscal.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        conn.commit(); conn.close()
        self.service = FiscalService(lambda: sqlite3.connect(self.db_path), storage_dir=Path(self.tmp.name) / "docs")

    def tearDown(self):
        self.tmp.cleanup()

    def test_armazenamento_registra_hashes_e_valida_integridade(self):
        key = "1" * 44
        request = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00"/></NFe>'
        response_xml = f'<ret><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe><nProt>12345</nProt></infProt></protNFe></ret>'
        response = FiscalResponse(True, "100", "Autorizado", "12345", raw_xml=response_xml, access_key=key)
        record = self.service.store_document(
            access_key=key, model="55", environment="HOMOLOGACAO",
            request_xml=request, response=response, actor="admin",
        )
        self.assertEqual(len(record["request_sha256"]), 64)
        self.assertEqual(len(record["response_sha256"]), 64)
        self.assertEqual(len(record["processed_sha256"]), 64)
        result = self.service.verify_document_integrity(access_key=key, environment="HOMOLOGACAO")
        self.assertTrue(result["valid"])

    def test_integridade_detecta_arquivo_fiscal_adulterado(self):
        key = "2" * 44
        response = FiscalResponse(False, "204", "Duplicidade", "", raw_xml="<ret><cStat>204</cStat></ret>", access_key=key)
        record = self.service.store_document(
            access_key=key, model="55", environment="HOMOLOGACAO",
            request_xml="<NFe/>", response=response, actor="admin",
        )
        Path(record["request_path"]).write_text("<NFe adulterada='1'/>", encoding="utf-8")
        result = self.service.verify_document_integrity(access_key=key)
        self.assertFalse(result["valid"])
        self.assertFalse(result["checks"]["request"]["valid"])


class FiscalEventEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "fiscal.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        conn.commit(); conn.close()
        self.service = FiscalService(lambda: sqlite3.connect(self.db_path), storage_dir=Path(self.tmp.name) / "docs")
        self.key = "29260812345678000195550010000000011000000010"
        request = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{self.key}" versao="4.00"/></NFe>'
        response_xml = f'<ret><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{self.key}</chNFe><nProt>12345</nProt></infProt></protNFe></ret>'
        response = FiscalResponse(True, "100", "Autorizado", "12345", raw_xml=response_xml, access_key=self.key)
        self.service.store_document(access_key=self.key, model="55", environment="HOMOLOGACAO", request_xml=request, response=response, actor="admin")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cancelamento_exige_protocolo_do_documento(self):
        with self.assertRaisesRegex(ValueError, "protocolo de autorização"):
            self.service.validate_event_eligibility(access_key=self.key, event_type="CANCELAMENTO", sequence=1, protocol="999")
        record = self.service.validate_event_eligibility(access_key=self.key, event_type="CANCELAMENTO", sequence=1, protocol="12345")
        self.assertEqual(record["protocol"], "12345")

    def test_sequencia_aceita_nao_pode_ser_reutilizada(self):
        xml, _ = self.service.build_event_xml(event_type="CCE", access_key=self.key, sequence=1, actor_document="12345678000195", correction="CORRECAO COM TEXTO SUFICIENTE", environment="HOMOLOGACAO")
        response = FiscalResponse(True, "135", "Evento registrado", "EVT1", raw_xml="<ret><cStat>135</cStat><nProt>EVT1</nProt></ret>")
        self.service.register_event(access_key=self.key, event_type="CCE", response=response, request_xml=xml, actor="admin")
        with self.assertRaisesRegex(ValueError, "Sequência de evento já utilizada"):
            self.service.validate_event_eligibility(access_key=self.key, event_type="CCE", sequence=1)

    def test_cce_e_bloqueada_apos_cancelamento_aceito(self):
        xml, _ = self.service.build_event_xml(event_type="CANCELAMENTO", access_key=self.key, sequence=1, actor_document="12345678000195", protocol="12345", justification="CANCELAMENTO COM JUSTIFICATIVA", environment="HOMOLOGACAO")
        response = FiscalResponse(True, "135", "Evento registrado", "CANCEL1", raw_xml="<ret><cStat>135</cStat><nProt>CANCEL1</nProt></ret>")
        self.service.register_event(access_key=self.key, event_type="CANCELAMENTO", response=response, request_xml=xml, actor="admin")
        with self.assertRaisesRegex(ValueError, "após cancelamento"):
            self.service.validate_event_eligibility(access_key=self.key, event_type="CCE", sequence=2)

    def test_cancelamento_aceito_atualiza_ciclo_de_vida_do_documento(self):
        xml, _ = self.service.build_event_xml(
            event_type="CANCELAMENTO", access_key=self.key, sequence=1,
            actor_document="12345678000195", protocol="12345",
            justification="CANCELAMENTO COM JUSTIFICATIVA", environment="HOMOLOGACAO",
        )
        response = FiscalResponse(
            True, "135", "Evento registrado", "CANCEL1",
            raw_xml="<ret><cStat>135</cStat><nProt>CANCEL1</nProt></ret>",
        )
        event = self.service.register_event(
            access_key=self.key, event_type="CANCELAMENTO",
            response=response, request_xml=xml, actor="admin",
        )
        document = [row for row in self.service.list_documents() if row["access_key"] == self.key][-1]
        self.assertEqual(document["status"], "CANCELADO")
        self.assertEqual(document["cancellation_protocol"], "CANCEL1")
        self.assertEqual(document["cancelled_by"], "admin")
        self.assertEqual(document["cancellation_request_sha256"], event["request_sha256"])
        self.assertEqual(document["cancellation_response_sha256"], event["response_sha256"])

    def test_evento_rejeitado_nao_altera_status_do_documento(self):
        xml, _ = self.service.build_event_xml(
            event_type="CANCELAMENTO", access_key=self.key, sequence=1,
            actor_document="12345678000195", protocol="12345",
            justification="CANCELAMENTO COM JUSTIFICATIVA", environment="HOMOLOGACAO",
        )
        response = FiscalResponse(
            False, "573", "Duplicidade de evento", "",
            raw_xml="<ret><cStat>573</cStat><xMotivo>Duplicidade</xMotivo></ret>",
        )
        self.service.register_event(
            access_key=self.key, event_type="CANCELAMENTO",
            response=response, request_xml=xml, actor="admin",
        )
        document = [row for row in self.service.list_documents() if row["access_key"] == self.key][-1]
        self.assertEqual(document["status"], "AUTORIZADO")

class FiscalAuthorizationNumberingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "fiscal-numbering.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        conn.commit()
        conn.close()
        self.service = FiscalService(lambda: sqlite3.connect(self.db_path), storage_dir=Path(self.tmp.name) / "docs")
        self.password = "senha-fiscal"
        self.pfx_path = Path(self.tmp.name) / "certificado.pfx"
        FiscalServiceTests._create_pfx(self.pfx_path, self.password)

    def tearDown(self):
        self.tmp.cleanup()

    def _configure(self):
        self.service.save_config({
            "enabled": True,
            "environment": "HOMOLOGACAO",
            "cnpj": "12345678000195",
            "state": "BA",
            "tax_regime": "SIMPLES",
            "certificate_path": str(self.pfx_path),
            "endpoints": {"HOMOLOGACAO": {"autorizacao": "https://sefaz.invalid/aut"}},
        })

    def _document(self, number: int):
        return self.service.build_document_xml(
            issuer={"cnpj":"12345678000195","name":"EMPRESA","city_code":"2925105","city":"SALVADOR","state":"BA","street":"RUA","number":"1","district":"CENTRO","zip_code":"40000000","state_registration":"123","tax_regime_code":1},
            recipient={"document":"12345678901","name":"CLIENTE"},
            items=[{"code":"P1","description":"PRODUTO","quantity":1,"unit_price":10,"ncm":"94036000","cfop":"5102","unit":"UN"}],
            document={"model":"55","series":1,"number":number,"state_code":"29","environment":"HOMOLOGACAO","numeric_code":"87654321"},
        )

    def test_autorizacao_confirma_reserva_somente_com_sucesso(self):
        self._configure()
        reservation = self.service.reserve_number(model="55", series=1, actor="admin")
        xml, key = self._document(reservation["number"])
        original = self.service.transmit
        self.service.transmit = lambda **_: FiscalResponse(
            True,
            "100",
            "Autorizado",
            "12345",
            raw_xml=f'<ret><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe><nProt>12345</nProt></infProt></protNFe></ret>',
            access_key=key,
        )
        try:
            _, record = self.service.authorize_document(
                xml=xml,
                access_key=key,
                password=self.password,
                actor="admin",
                reservation_id=reservation["id"],
            )
        finally:
            self.service.transmit = original
        self.assertEqual(record["numbering"]["status"], "CONFIRMADO")
        status = self.service.numbering_status(model="55", series=1)
        self.assertEqual(status[0]["access_key"], key)

    def test_rejeicao_nao_confirma_reserva(self):
        self._configure()
        reservation = self.service.reserve_number(model="55", series=1, actor="admin")
        xml, key = self._document(reservation["number"])
        original = self.service.transmit
        self.service.transmit = lambda **_: FiscalResponse(
            False,
            "539",
            "Duplicidade",
            "",
            raw_xml='<ret><cStat>539</cStat><xMotivo>Duplicidade</xMotivo></ret>',
            access_key=key,
        )
        try:
            response, _ = self.service.authorize_document(
                xml=xml,
                access_key=key,
                password=self.password,
                actor="admin",
                reservation_id=reservation["id"],
            )
        finally:
            self.service.transmit = original
        self.assertFalse(response.success)
        status = self.service.numbering_status(model="55", series=1)
        self.assertEqual(status[0]["status"], "RESERVADO")
        self.assertEqual(status[0]["access_key"], "")


class FiscalAuthorizedStorageConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "fiscal-storage.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        conn.commit()
        conn.close()
        self.service = FiscalService(
            lambda: sqlite3.connect(self.db_path),
            storage_dir=Path(self.tmp.name) / "docs",
        )
        self.key = "29260812345678000195550010000000011000000010"

    def tearDown(self):
        self.tmp.cleanup()

    def test_autorizacao_sem_protocolo_mesclavel_nao_e_indexada(self):
        request = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{self.key}" versao="4.00"/></NFe>'
        # cStat e nProt existem, mas não há protNFe completo para formar nfeProc.
        response = FiscalResponse(
            True, "100", "Autorizado", "12345",
            raw_xml=f'<ret><cStat>100</cStat><nProt>12345</nProt><chNFe>{self.key}</chNFe></ret>',
            access_key=self.key,
        )
        with self.assertRaisesRegex(ValueError, "protocolo completos"):
            self.service.store_document(
                access_key=self.key, model="55", environment="HOMOLOGACAO",
                request_xml=request, response=response, actor="admin",
            )
        self.assertEqual(self.service.list_documents(), [])
        folder = Path(self.tmp.name) / "docs" / "homologacao" / "55" / self.key
        self.assertFalse((folder / "envio.xml").exists())
        self.assertFalse((folder / "retorno.xml").exists())
        self.assertFalse((folder / "processado.xml").exists())

    def test_arquivos_fiscais_sao_gravados_atomicamente(self):
        request = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{self.key}" versao="4.00"/></NFe>'
        response_xml = f'<ret><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{self.key}</chNFe><nProt>12345</nProt></infProt></protNFe></ret>'
        response = FiscalResponse(True, "100", "Autorizado", "12345", raw_xml=response_xml, access_key=self.key)
        record = self.service.store_document(
            access_key=self.key, model="55", environment="HOMOLOGACAO",
            request_xml=request, response=response, actor="admin",
        )
        self.assertEqual(record["status"], "AUTORIZADO")
        self.assertTrue(Path(record["processed_path"]).is_file())
        folder = Path(record["processed_path"]).parent
        self.assertEqual(list(folder.glob("*.tmp")), [])
        self.assertEqual(list(folder.glob(".*.tmp")), [])
