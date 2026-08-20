from __future__ import annotations

import base64
import csv
import hashlib
import json
import sqlite3
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from services.fiscal_service import (
    FiscalResponse,
    FiscalService,
    InvalidCertificatePasswordError,
)
from services.fiscal_preflight_service import FiscalPreflightService
from services.pdv_service import PDVService


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

    def test_producao_fica_bloqueada_ate_homologar_ibs_cbs(self):
        self.service.save_config({"enabled": True, "environment": "PRODUCAO"})
        problems = self.service.validate_ready(operation="autorizacao", model="55")
        self.assertTrue(any("IBS/CBS" in problem for problem in problems))

    def test_transmissao_direta_em_producao_falha_fechado_sem_status_de_revogacao(self):
        self.service.http_post = lambda *_args, **_kwargs: self.fail("não deve transmitir")
        self.service.save_config({
            "environment": "PRODUCAO",
            "endpoints": {"PRODUCAO": {"autorizacao": "https://sefaz.invalid/autorizacao"}},
        })
        trusted = type("Trust", (), {"trusted": True, "message": "Cadeia válida."})()
        unknown = type("Revocation", (), {
            "good": False, "message": "CRL indisponível para validação."
        })()
        with patch.object(self.service, "validate_certificate_trust", return_value=trusted), patch.object(
            self.service, "check_certificate_revocation", return_value=unknown
        ), self.assertRaisesRegex(ValueError, "Situação de revogação não confirmada"):
            self.service.transmit(
                operation="autorizacao", xml=b"<xml/>",
                pfx_path=self.pfx_path, password=self.password,
            )

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

    def test_consulta_status_sefaz_sem_emitir_ou_reservar_numero(self):
        calls = []

        class Response:
            content = b"""<retConsStatServ xmlns='http://www.portalfiscal.inf.br/nfe'>
                <tpAmb>2</tpAmb><verAplic>TESTE</verAplic><cStat>107</cStat>
                <xMotivo>Servico em Operacao</xMotivo><cUF>29</cUF>
            </retConsStatServ>"""

            @staticmethod
            def raise_for_status():
                return None

        def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response()

        self.service.http_post = post
        self.service.save_config({
            "cnpj": "12345678000195", "state": "BA", "environment": "HOMOLOGACAO",
            "enabled_models": ["55", "65"], "default_model": "65",
            "certificate_path": str(self.pfx_path),
        })
        result = self.service.check_service_status(model="65", password=self.password)
        self.assertTrue(result.available)
        self.assertEqual(result.status_code, "107")
        self.assertIn("NfeStatusServico", calls[0][0])
        self.assertIn(b"consStatServ", calls[0][1]["data"])
        self.assertEqual(self.service.numbering_status(), [])

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
        self.assertEqual(info.company_name, "EMPRESA TESTE")
        self.assertTrue(info.expiring_soon)
        self.assertGreaterEqual(info.expires_in_days, 29)
        self.assertEqual(self.service.validate_ready(operation="autorizacao"), [])

    def test_certificado_rejeita_extensao_e_senha_invalidas(self):
        wrong_extension = Path(self.tmp.name) / "certificado.txt"
        wrong_extension.write_bytes(self.pfx_path.read_bytes())
        with self.assertRaisesRegex(ValueError, r"\.pfx ou \.p12"):
            self.service.inspect_certificate(wrong_extension, self.password)
        with self.assertRaises(InvalidCertificatePasswordError):
            self.service.inspect_certificate(self.pfx_path, "senha-incorreta")

    def test_certificado_configurado_reutiliza_senha_somente_na_sessao(self):
        self.service.configure_certificate(self.pfx_path, self.password)
        self.assertIsNone(self.service.session_certificate_password())
        info = self.service.cache_certificate_password(self.password)
        self.assertEqual(info.document, "12345678000195")
        self.assertEqual(self.service.session_certificate_password(), self.password)
        self.service.clear_session_certificate_password()
        self.assertIsNone(self.service.session_certificate_password())
        config_text = json.dumps(self.service.load_config(), ensure_ascii=False)
        self.assertNotIn(self.password, config_text)

    def test_instalacao_segura_gerencia_copia_senha_e_remocao(self):
        class FakeProtector:
            def protect(self, data):
                return b"PROTECTED:" + bytes(data)[::-1]

            def unprotect(self, data):
                assert data.startswith(b"PROTECTED:")
                return data.removeprefix(b"PROTECTED:")[::-1]

        storage = Path(self.tmp.name) / "cofre_fiscal"
        service = FiscalService(
            self.connect, storage_dir=storage, secret_protector=FakeProtector()
        )
        service.save_config({"cnpj": "12345678000195"})
        info = service.install_certificate_securely(self.pfx_path, self.password)
        config = service.load_config()
        managed = Path(config["certificate_path"])
        self.assertTrue(config["certificate_managed"])
        self.assertTrue(managed.is_file())
        self.assertNotEqual(managed.resolve(), self.pfx_path.resolve())
        self.assertTrue(self.pfx_path.is_file())
        secret_path = storage / "certificate" / "active.secret"
        self.assertNotEqual(secret_path.read_bytes(), self.password.encode())
        service.clear_session_certificate_password()
        self.assertEqual(service.session_certificate_password(), self.password)
        self.assertEqual(info.company_name, "EMPRESA TESTE")
        service.remove_managed_certificate()
        self.assertFalse(managed.exists())
        self.assertFalse(secret_path.exists())
        self.assertTrue(self.pfx_path.is_file())
        self.assertFalse(service.load_config()["certificate_managed"])

    def test_senha_incorreta_nao_e_guardada_na_sessao(self):
        self.service.configure_certificate(self.pfx_path, self.password)
        with self.assertRaises(ValueError):
            self.service.cache_certificate_password("senha-errada")
        self.assertIsNone(self.service.session_certificate_password())

    def test_pre_voo_real_assina_e_valida_sem_transmitir(self):
        conn = self.connect()
        conn.execute(
            """CREATE TABLE produtos (
                id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, ncm TEXT, cest TEXT, cfop TEXT,
                fiscal_origin TEXT, fiscal_csosn TEXT, fiscal_icms_cst TEXT, fiscal_icms_rate TEXT,
                fiscal_pis_cst TEXT, fiscal_pis_rate TEXT, fiscal_cofins_cst TEXT, fiscal_cofins_rate TEXT,
                fiscal_profile_source TEXT, ibs_cbs_cst TEXT, ibs_cbs_class TEXT,
                ibs_uf_rate TEXT, ibs_city_rate TEXT, cbs_rate TEXT
            )"""
        )
        conn.execute(
            """INSERT INTO produtos VALUES(
                1,'P1','PRODUTO','94036000','','5102','0','102','','0','07','0','07','0','MANUAL',
                '000','000001','0.1','0','0.9')"""
        )
        conn.commit(); conn.close()
        self.service.save_config({
            "enabled": True, "environment": "HOMOLOGACAO", "default_model": "65",
            "enabled_models": ["55", "65"], "cnpj": "12345678000195", "state": "BA",
            "tax_regime": "SIMPLES_NACIONAL", "certificate_path": str(self.pfx_path),
            "issuer": {
                "name": "EMPRESA TESTE", "state_registration": "123", "city_code": "2927408",
                "city": "SALVADOR", "street": "RUA TESTE", "number": "1",
                "district": "CENTRO", "zip_code": "40000000",
            },
        })
        self.service.configure_certificate(self.pfx_path, self.password)

        class ReadyCatalog:
            def audit(_self, *, crt):
                self.assertEqual(crt, 1)
                return type("Report", (), {
                    "total": 1, "ready": 1, "blocked": 0, "ready_product_ids": (1,)
                })()

        with patch.object(
            self.service,
            "validate_certificate_trust",
            return_value=type("Trust", (), {"trusted": True, "message": "Cadeia de teste válida."})(),
        ):
            result = FiscalPreflightService(self.service, ReadyCatalog()).run(password=self.password)
        self.assertTrue(result.success, result.problems)
        self.assertEqual(result.catalog_ready, 1)
        self.assertEqual(result.certificate_document, "12345678000195")
        self.assertEqual(len(result.xml_sha256), 64)
        self.assertEqual(result.validated_models, ("55", "65"))
        self.assertEqual(len(result.xml_sha256_by_model), 2)
        self.assertEqual(self.service.list_transmission_queue(), [])

    def test_configuracao_preserva_cnpj_alfanumerico_oficial(self):
        config = self.service.save_config({"cnpj": "12.ABC.345/01DE-35"})
        self.assertEqual(config["cnpj"], "12ABC34501DE35")
        self.assertTrue(self.service._is_valid_cnpj_format(config["cnpj"]))
        self.assertTrue(self.service._is_valid_cnpj(config["cnpj"]))

    def test_cnpj_alfanumerico_com_digito_incorreto_e_rejeitado(self):
        self.assertFalse(self.service._is_valid_cnpj("12.ABC.345/01DE-34"))

    def test_chave_de_acesso_preserva_cnpj_alfanumerico(self):
        key = self.service.build_access_key(
            state_code="29",
            issued_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
            cnpj="12.ABC.345/01DE-35",
            model="55",
            series=1,
            number=1,
            numeric_code="12345678",
        )
        self.assertEqual(len(key), 44)
        self.assertEqual(key[6:20], "12ABC34501DE35")
        self.assertEqual(key[-1], self.service.calculate_access_key_digit(key[:43]))
        self.assertTrue(self.service._is_valid_access_key(key))

    def test_normalizacao_nao_remove_letras_de_chave_fiscal(self):
        key = "29260812ABC34501DE35550010000000011123456789"
        self.assertEqual(self.service._normalize_access_key(key.lower()), key)

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

    def test_configuracao_preserva_series_de_venda_por_modelo(self):
        config = self.service.save_config({"sale_series_55": "2", "sale_series_65": "7"})
        self.assertEqual(config["sale_series_55"], 2)
        self.assertEqual(config["sale_series_65"], 7)
        loaded = self.service.load_config()
        self.assertEqual((loaded["sale_series_55"], loaded["sale_series_65"]), (2, 7))

    def test_configuracao_rejeita_serie_de_venda_fora_do_intervalo(self):
        with self.assertRaisesRegex(ValueError, "entre 0 e 999"):
            self.service.save_config({"sale_series_65": 1000})

    def test_numeração_inicial_define_proximo_numero_uma_unica_vez(self):
        initialized = self.service.initialize_numbering(
            model="55", series=4, next_number=321, environment="HOMOLOGACAO",
            actor="admin",
        )
        self.assertEqual(initialized["next_number"], 321)
        scope = self.service.numbering_scope(
            model="55", series=4, environment="HOMOLOGACAO"
        )
        self.assertTrue(scope["initialized"])
        self.assertEqual(scope["next_number"], 321)
        reserved = self.service.reserve_number(
            model="55", series=4, environment="HOMOLOGACAO", actor="admin"
        )
        self.assertEqual(reserved["number"], 321)
        with self.assertRaisesRegex(ValueError, "já foi iniciada"):
            self.service.initialize_numbering(
                model="55", series=4, next_number=500,
                environment="HOMOLOGACAO", actor="admin",
            )

    def test_numeração_inicial_isola_ambiente_modelo_e_serie(self):
        self.service.initialize_numbering(
            model="65", series=2, next_number=90,
            environment="HOMOLOGACAO", actor="admin",
        )
        production = self.service.numbering_scope(
            model="65", series=2, environment="PRODUCAO"
        )
        other_model = self.service.numbering_scope(
            model="55", series=2, environment="HOMOLOGACAO"
        )
        self.assertFalse(production["initialized"])
        self.assertFalse(other_model["initialized"])

    def test_bahia_oferece_todos_os_regimes_e_os_dois_modelos(self):
        expected_regimes = {
            "MEI": 4,
            "SIMPLES_NACIONAL": 1,
            "EXCESSO_SUBLIMITE": 2,
            "LUCRO_PRESUMIDO": 3,
            "LUCRO_REAL": 3,
        }
        for regime, crt in expected_regimes.items():
            with self.subTest(regime=regime):
                config = self.service.save_config({
                    "state": "BA",
                    "tax_regime": regime,
                    "enabled_models": ["55", "65"],
                    "default_model": "65",
                })
                self.assertEqual(self.service.TAX_REGIME_CODES[config["tax_regime"]], crt)
                self.assertEqual(config["enabled_models"], ["55", "65"])
                self.assertEqual(config["default_model"], "65")

    def test_indice_fiscal_nao_descarta_documentos_antigos(self):
        key = "29260812345678000195650010000000011000000017"
        rows = [
            {
                "access_key": f"{position:044d}",
                "environment": "HOMOLOGACAO",
                "status": "AUTORIZADO",
                "protocol": str(position),
            }
            for position in range(1001)
        ]
        rows[-1].update({"access_key": key, "protocol": "123", "status": "AUTORIZADO"})
        self.service._set_setting(
            self.service.DOCUMENT_INDEX_KEY,
            json.dumps(rows, ensure_ascii=False),
        )

        self.service._mark_document_cancelled(
            access_key=key,
            event_protocol="456",
            actor="admin",
            event_record={"status_code": "135", "message": "Evento registrado"},
        )

        persisted = self.service.list_documents()
        self.assertEqual(len(persisted), 1001)
        self.assertEqual(persisted[0]["access_key"], f"{0:044d}")
        self.assertEqual(persisted[-1]["status"], "CANCELADO")

    def test_modelo_padrao_precisa_estar_habilitado(self):
        with self.assertRaisesRegex(ValueError, "modelo fiscal padrão"):
            self.service.save_config({"enabled_models": ["55"], "default_model": "65"})

    def test_bahia_separa_endpoints_oficiais_nfe_e_nfce(self):
        self.service.save_config({"state": "BA", "environment": "HOMOLOGACAO", "endpoints": {}})
        self.assertIn("hnfe.sefaz.ba.gov.br", self.service.endpoint("autorizacao", model="55"))
        self.assertIn("nfce-homologacao.svrs.rs.gov.br", self.service.endpoint("autorizacao", model="65"))
        self.service.save_config({"state": "BA", "environment": "PRODUCAO", "endpoints": {}})
        self.assertIn("nfe.sefaz.ba.gov.br", self.service.endpoint("consulta", model="55"))
        self.assertIn("nfce.svrs.rs.gov.br", self.service.endpoint("consulta", model="65"))

    def test_catalogo_nacional_cobre_27_ufs_sem_liberar_perfis_nao_homologados(self):
        profiles = self.service.state_catalog()
        self.assertEqual(len(profiles), 27)
        self.assertEqual({item["uf"] for item in profiles}, set(self.service.STATE_CODES))
        self.assertEqual(self.service.state_profile("BA")["status"], "VALIDADO")
        self.assertEqual(self.service.state_profile("SP")["nfe_authorizer"], "SP")
        self.assertEqual(self.service.state_profile("RJ")["nfe_authorizer"], "SVRS")
        self.assertEqual(self.service.state_profile("MA")["nfe_authorizer"], "SVAN")

    def test_uf_preparada_sem_homologacao_e_bloqueada_com_mensagem_clara(self):
        self.service.save_config({"enabled": True, "state": "SP", "environment": "HOMOLOGACAO"})
        problems = self.service.validate_ready(operation="autorizacao", model="55")
        self.assertTrue(any("preparada" in problem and "não homologada" in problem for problem in problems))
        self.assertEqual(self.service.endpoint("autorizacao", model="55"), "")

    def test_endpoint_manual_preserva_prioridade_sobre_catalogo_oficial(self):
        custom = "https://sefaz.invalid/custom"
        self.service.save_config({
            "state": "BA", "environment": "HOMOLOGACAO",
            "endpoints": {"HOMOLOGACAO": {"autorizacao": custom}},
        })
        self.assertEqual(self.service.endpoint("autorizacao", model="55"), custom)

    def test_fila_nao_duplica_autorizacao_da_mesma_chave(self):
        key = "29" + "0" * 18 + "65" + "0" * 22
        xml = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}"/></NFe>'
        first = self.service.enqueue_transmission(
            operation="autorizacao", xml=xml, actor="caixa", access_key=key, model="65"
        )
        second = self.service.enqueue_transmission(
            operation="autorizacao", xml=xml, actor="caixa", access_key=key, model="65"
        )
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.service.list_transmission_queue()), 1)

    def test_validador_cpf_recusa_sequencia_e_aceita_digitos_validos(self):
        self.assertTrue(self.service._is_valid_cpf("529.982.247-25"))
        self.assertFalse(self.service._is_valid_cpf("111.111.111-11"))
        self.assertFalse(self.service._is_valid_cpf("529.982.247-24"))

    def test_endpoint_manual_bloqueia_destino_capaz_de_capturar_certificado(self):
        invalid_endpoints = (
            "http://nfe.sefaz.ba.gov.br/autorizacao",
            "https://usuario:senha@nfe.sefaz.ba.gov.br/autorizacao",
            "https://nfe.sefaz.ba.gov.br:8443/autorizacao",
            "https://nfe.sefaz.ba.gov.br/autorizacao?destino=externo",
            "https://coletor.exemplo.com/autorizacao",
        )
        for endpoint in invalid_endpoints:
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(ValueError, "Endpoint fiscal"):
                    self.service.save_config({
                        "endpoints": {"HOMOLOGACAO": {"autorizacao": endpoint}}
                    })

    def test_endpoint_inseguro_persistido_anteriormente_e_bloqueado_no_uso(self):
        config = self.service.load_config()
        config["endpoints"] = {
            "HOMOLOGACAO": {"autorizacao": "https://coletor.exemplo.com/a"},
            "PRODUCAO": {},
        }
        self.service._set_setting(
            self.service.CONFIG_KEY,
            json.dumps(config, ensure_ascii=False),
        )
        with self.assertRaisesRegex(ValueError, "domínio governamental"):
            self.service.endpoint("autorizacao", model="55")

    def test_validacao_recusa_modelo_desabilitado(self):
        self.service.save_config({"enabled": True, "enabled_models": ["55"], "default_model": "55"})
        self.assertTrue(any("não está habilitado" in problem for problem in self.service.validate_ready(operation="autorizacao", model="65")))

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
        self.assertEqual(root.xpath("string(//*[local-name()='dest']/*[local-name()='indIEDest'])"), "9")
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

    def test_gera_ibs_cbs_normal_e_totais_conforme_schema_oficial(self):
        xml, _key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA TESTE", "number": "10",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={"document": "12345678901", "name": "CLIENTE TESTE"},
            items=[{
                "code": "P1", "description": "produto rtc", "quantity": 2, "unit_price": 50,
                "ncm": "94036000", "cfop": "5102", "unit": "UN",
                "ibs_cbs_cst": "000", "ibs_cbs_class": "000001",
                "ibs_uf_rate": "0.1000", "ibs_city_rate": "0.0000", "cbs_rate": "0.9000",
            }],
            document={
                "model": "55", "series": 1, "number": 13, "state_code": "29",
                "issued_at": datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc),
                "environment": "HOMOLOGACAO", "numeric_code": "12345679",
            },
        )
        root = etree.fromstring(xml)
        self.assertEqual(root.xpath("string(//*[local-name()='IBSCBS']/*[local-name()='CST'])"), "000")
        self.assertEqual(root.xpath("string(//*[local-name()='gIBSUF']/*[local-name()='vIBSUF'])"), "0.10")
        self.assertEqual(root.xpath("string(//*[local-name()='gCBS']/*[local-name()='vCBS'])"), "0.90")
        self.assertEqual(root.xpath("string(//*[local-name()='vNFTot'])"), "101.00")
        signed = self.service.sign_xml(
            xml, reference_id=f"NFe{_key}", pfx_path=self.pfx_path, password=self.password
        )
        self.assertEqual(self.service.validate_xml_schema(signed, self.service.official_schema_path("nfe")), [])

    def test_ficha_simples_com_st_gera_icmssn500_e_contribuicoes_nt(self):
        xml, _key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA", "number": "1",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={"document": "12345678901", "name": "CLIENTE TESTE"},
            items=[{
                "code": "P1", "description": "produto st", "quantity": 1, "unit_price": 100,
                "ncm": "94036000", "cest": "0100100", "cfop": "5405", "unit": "UN",
                "origin": "0", "csosn": "500", "pis_cst": "07", "cofins_cst": "07",
            }],
            document={
                "model": "55", "series": 1, "number": 14, "state_code": "29",
                "environment": "HOMOLOGACAO", "numeric_code": "12345671",
                "strict_tax_profile": True,
            },
        )
        root = etree.fromstring(xml)
        self.assertEqual(root.xpath("string(//*[local-name()='ICMSSN500']/*[local-name()='CSOSN'])"), "500")
        self.assertEqual(root.xpath("string(//*[local-name()='CEST'])"), "0100100")
        self.assertEqual(root.xpath("string(//*[local-name()='PISNT']/*[local-name()='CST'])"), "07")
        self.assertEqual(root.xpath("string(//*[local-name()='COFINSNT']/*[local-name()='CST'])"), "07")

    def test_mei_crt4_gera_grupo_do_simples_com_csosn(self):
        xml, _key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA", "number": "1",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 4,
            },
            recipient={"document": "12345678901", "name": "CLIENTE TESTE"},
            items=[{
                "code": "P1", "description": "produto mei", "quantity": 1, "unit_price": 20,
                "ncm": "94036000", "cfop": "5102", "unit": "UN", "origin": "0",
                "csosn": "102", "pis_cst": "07", "cofins_cst": "07",
            }],
            document={
                "model": "55", "series": 1, "number": 16, "state_code": "29",
                "environment": "HOMOLOGACAO", "numeric_code": "12345673",
                "strict_tax_profile": True,
            },
        )
        root = etree.fromstring(xml)
        self.assertEqual(root.xpath("string(//*[local-name()='emit']/*[local-name()='CRT'])"), "4")
        self.assertEqual(root.xpath("string(//*[local-name()='ICMSSN102']/*[local-name()='CSOSN'])"), "102")
        self.assertEqual(root.xpath("count(//*[local-name()='ICMS00'])"), 0.0)

    def test_ficha_regime_normal_calcula_icms_pis_e_cofins(self):
        xml, _key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA", "number": "1",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 3,
            },
            recipient={"document": "12345678901", "name": "CLIENTE TESTE"},
            items=[{
                "code": "P1", "description": "produto tributado", "quantity": 2, "unit_price": 50,
                "ncm": "94036000", "cfop": "5102", "unit": "UN", "origin": "0",
                "cst": "00", "icms_rate": "18", "pis_cst": "01", "pis_rate": "1.65",
                "cofins_cst": "01", "cofins_rate": "7.6",
            }],
            document={
                "model": "55", "series": 1, "number": 15, "state_code": "29",
                "environment": "HOMOLOGACAO", "numeric_code": "12345672",
                "strict_tax_profile": True,
            },
        )
        root = etree.fromstring(xml)
        self.assertEqual(root.xpath("string(//*[local-name()='ICMS00']/*[local-name()='vICMS'])"), "18.00")
        self.assertEqual(root.xpath("string(//*[local-name()='PISAliq']/*[local-name()='vPIS'])"), "1.65")
        self.assertEqual(root.xpath("string(//*[local-name()='COFINSAliq']/*[local-name()='vCOFINS'])"), "7.60")

    def test_prepara_itens_da_venda_com_ficha_fiscal_automatica(self):
        conn = self.connect()
        conn.execute(
            """CREATE TABLE produtos (
                id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, ncm TEXT, cest TEXT, cfop TEXT,
                fiscal_origin TEXT, fiscal_csosn TEXT, fiscal_icms_cst TEXT, fiscal_icms_rate TEXT,
                fiscal_pis_cst TEXT, fiscal_pis_rate TEXT, fiscal_cofins_cst TEXT, fiscal_cofins_rate TEXT,
                fiscal_profile_source TEXT,
                ibs_cbs_cst TEXT, ibs_cbs_class TEXT,
                ibs_uf_rate TEXT, ibs_city_rate TEXT, cbs_rate TEXT
            )"""
        )
        conn.execute(
            """INSERT INTO produtos VALUES(
                1,'P1','PRODUTO','94036000','','5102','0','102','','0','07','0','07','0','XML_IMPORT',
                '000','000001','0.1','0','0.9')"""
        )
        conn.commit(); conn.close()
        items = self.service.prepare_sale_items(
            [{"produto_id": 1, "item": "Produto", "qtd": 2, "preco": 10}], destination=2
        )
        self.assertEqual(items[0]["cfop"], "6102")
        self.assertEqual(items[0]["ncm"], "94036000")
        self.assertEqual(items[0]["ibs_cbs_class"], "000001")
        self.assertEqual(items[0]["cbs_rate"], "0.9")
        export_items = self.service.prepare_sale_items(
            [{"produto_id": 1, "item": "Produto", "qtd": 2, "preco": 10}], destination=3
        )
        self.assertEqual(export_items[0]["cfop"], "7102")
        self.assertEqual(export_items[0]["ibs_cbs_cst"], "410")
        self.assertEqual(export_items[0]["ibs_cbs_class"], "410004")
        self.assertEqual(export_items[0]["cbs_rate"], "0")

    def test_exportacao_gera_ibs_cbs_sem_incidencia_e_valida_no_xsd(self):
        xml, key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA", "number": "1",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={"foreign_id": "EX123", "name": "CLIENTE EXTERIOR"},
            items=[{
                "code": "P1", "description": "produto exportado", "quantity": 1, "unit_price": 100,
                "ncm": "94036000", "cfop": "7102", "unit": "UN", "origin": "0",
                "csosn": "102", "pis_cst": "07", "cofins_cst": "07",
                "ibs_cbs_cst": "410", "ibs_cbs_class": "410004",
            }],
            document={
                "model": "55", "series": 1, "number": 17, "state_code": "29",
                "environment": "HOMOLOGACAO", "numeric_code": "12345674",
                "destination": 3, "strict_tax_profile": True,
            },
        )
        root = etree.fromstring(xml)
        self.assertEqual(root.xpath("string(//*[local-name()='IBSCBS']/*[local-name()='CST'])"), "410")
        self.assertEqual(root.xpath("string(//*[local-name()='IBSCBS']/*[local-name()='cClassTrib'])"), "410004")
        self.assertEqual(root.xpath("count(//*[local-name()='IBSCBS']/*[local-name()='gIBSCBS'])"), 0.0)
        signed = self.service.sign_xml(
            xml, reference_id=f"NFe{key}", pfx_path=self.pfx_path, password=self.password
        )
        self.assertEqual(self.service.validate_xml_schema(signed, self.service.official_schema_path("nfe")), [])

    def test_venda_fiscal_explica_ficha_incompleta_sem_salvar(self):
        conn = self.connect()
        conn.execute(
            """CREATE TABLE produtos (
                id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, ncm TEXT, cest TEXT, cfop TEXT,
                fiscal_origin TEXT, fiscal_csosn TEXT, fiscal_icms_cst TEXT, fiscal_icms_rate TEXT,
                fiscal_pis_cst TEXT, fiscal_pis_rate TEXT, fiscal_cofins_cst TEXT, fiscal_cofins_rate TEXT,
                fiscal_profile_source TEXT,
                ibs_cbs_cst TEXT, ibs_cbs_class TEXT,
                ibs_uf_rate TEXT, ibs_city_rate TEXT, cbs_rate TEXT
            )"""
        )
        conn.execute("INSERT INTO produtos(id,codigo,nome) VALUES(1,'P1','PRODUTO')")
        conn.commit(); conn.close()
        with self.assertRaisesRegex(ValueError, "ficha fiscal incompleta"):
            self.service.prepare_sale_items(
                [{"produto_id": 1, "item": "Produto", "qtd": 1, "preco": 10}]
            )

    def test_nfce_online_inclui_qrcode_v3_sem_csc(self):
        issued = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
        xml, key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA TESTE", "number": "10",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={},
            items=[{"code": "P1", "description": "produto", "quantity": 1, "unit_price": 10,
                    "ncm": "94036000", "cfop": "5102", "unit": "UN"}],
            document={"model": "65", "series": 1, "number": 1, "state_code": "29",
                      "issued_at": issued, "environment": "HOMOLOGACAO", "numeric_code": "12345678",
                      "final_consumer": 1, "presence": 1},
        )
        root = etree.fromstring(xml)
        qr_code = root.xpath("string(//*[local-name()='infNFeSupl']/*[local-name()='qrCode'])")
        self.assertEqual(
            qr_code,
            f"http://hnfe.sefaz.ba.gov.br/servicos/nfce/qrcode.aspx?p={key}|3|2",
        )
        self.assertNotIn("CSC", qr_code.upper())
        self.assertEqual(
            root.xpath("string(//*[local-name()='infNFeSupl']/*[local-name()='urlChave'])"),
            "http://hinternet.sefaz.ba.gov.br/nfce/consulta",
        )

    def test_pagamento_cartao_pos_gera_grupo_sem_exigir_autorizacao(self):
        xml, _key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA", "number": "1",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={},
            items=[{"code":"P1","description":"PRODUTO","quantity":1,"unit_price":10,
                    "ncm":"94036000","cfop":"5102","unit":"UN"}],
            document={"model":"65","series":1,"number":2,"state_code":"29",
                      "environment":"HOMOLOGACAO","numeric_code":"12345679",
                      "payment_code":"04","payment_detail":{"integration":2}},
        )
        root = etree.fromstring(xml)
        self.assertEqual(root.xpath("string(//*[local-name()='card']/*[local-name()='tpIntegra'])"), "2")
        self.assertEqual(root.xpath("string(//*[local-name()='card']/*[local-name()='cAut'])"), "")

    def test_pagamentos_mistos_e_troco_sao_gerados_no_xml(self):
        xml, _key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
                "city": "SALVADOR", "state": "BA", "street": "RUA", "number": "1",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={},
            items=[{"code":"P1","description":"PRODUTO","quantity":1,"unit_price":10,
                    "ncm":"94036000","cfop":"5102","unit":"UN"}],
            document={"model":"65","series":1,"number":3,"state_code":"29",
                      "environment":"HOMOLOGACAO","numeric_code":"12345670",
                      "payments":[
                          {"code":"17","amount":"4.00"},
                          {"code":"01","amount":"7.00"},
                      ]},
        )
        root = etree.fromstring(xml)
        self.assertEqual(
            root.xpath("//*[local-name()='detPag']/*[local-name()='tPag']/text()"),
            ["17", "01"],
        )
        self.assertEqual(
            root.xpath("//*[local-name()='detPag']/*[local-name()='vPag']/text()"),
            ["4.00", "7.00"],
        )
        self.assertEqual(root.xpath("string(//*[local-name()='pag']/*[local-name()='vTroco'])"), "1.00")

    def test_pagamento_fiscal_inferior_ao_total_e_bloqueado(self):
        issuer = {
            "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
            "city": "SALVADOR", "state": "BA", "street": "RUA", "number": "1",
            "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
            "tax_regime_code": 1,
        }
        items = [{"code":"P1","description":"PRODUTO","quantity":1,"unit_price":10,
                  "ncm":"94036000","cfop":"5102","unit":"UN"}]
        document = {"model":"65","series":1,"number":4,"state_code":"29",
                    "environment":"HOMOLOGACAO","numeric_code":"12345671",
                    "payments":[{"code":"17","amount":"9.99"}]}
        with self.assertRaisesRegex(ValueError, "menor"):
            self.service.build_document_xml(
                issuer=issuer, recipient={}, items=items, document=document
            )

    def test_sem_pagamento_nao_pode_ser_misturado(self):
        issuer = {
            "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2925105",
            "city": "SALVADOR", "state": "BA", "street": "RUA", "number": "1",
            "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
            "tax_regime_code": 1,
        }
        items = [{"code":"P1","description":"PRODUTO","quantity":1,"unit_price":10,
                  "ncm":"94036000","cfop":"5102","unit":"UN"}]
        document = {"model":"55","series":1,"number":5,"state_code":"29",
                    "environment":"HOMOLOGACAO","numeric_code":"12345672",
                    "payments":[{"code":"90","amount":"0"},{"code":"01","amount":"10"}]}
        with self.assertRaisesRegex(ValueError, "combinado"):
            self.service.build_document_xml(
                issuer=issuer, recipient={}, items=items, document=document
            )

    def test_nfce_offline_assina_parametros_qrcode_v3_com_certificado(self):
        issued = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
        key = self.service.build_access_key(
            state_code="29", issued_at=issued, cnpj="12345678000195", model="65",
            series=1, number=2, emission_type=9, numeric_code="12345679",
        )
        qr_code = self.service.build_nfce_qr_code_v3(
            access_key=key, environment="HOMOLOGACAO", issued_at=issued,
            total="10.00", recipient_document="12345678901",
            pfx_path=self.pfx_path, password=self.password,
        )
        parameters = qr_code.split("?p=", 1)[1].split("|")
        self.assertEqual(parameters[:7], [key, "3", "2", "18", "10.00", "2", "12345678901"])
        signed_payload = "|".join(parameters[:7]).encode("utf-8")
        signature = base64.b64decode(parameters[7])
        _private_key, certificate, _chain = pkcs12.load_key_and_certificates(
            self.pfx_path.read_bytes(), self.password.encode("utf-8")
        )
        certificate.public_key().verify(signature, signed_payload, padding.PKCS1v15(), hashes.SHA1())

    def test_qrcode_v3_rejeita_chave_nfe_e_offline_sem_certificado(self):
        issued = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
        nfe_key = self.service.build_access_key(
            state_code="29", issued_at=issued, cnpj="12345678000195", model="55",
            series=1, number=1, emission_type=1, numeric_code="12345678",
        )
        with self.assertRaisesRegex(ValueError, "modelo 65"):
            self.service.build_nfce_qr_code_v3(access_key=nfe_key, environment="HOMOLOGACAO")
        nfce_key = self.service.build_access_key(
            state_code="29", issued_at=issued, cnpj="12345678000195", model="65",
            series=1, number=1, emission_type=9, numeric_code="12345678",
        )
        with self.assertRaisesRegex(ValueError, "Certificado A1"):
            self.service.build_nfce_qr_code_v3(
                access_key=nfce_key, environment="HOMOLOGACAO", issued_at=issued, total="1.00"
            )

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

    def test_exportacao_contabil_separa_xmls_validos_e_eventos_por_periodo(self):
        now = datetime.now().astimezone()
        key = self.service.build_access_key(
            state_code="29", issued_at=now, cnpj="12345678000195", model="55",
            series=1, number=77, emission_type=1, numeric_code="76543210",
        )
        request = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00"/></NFe>'
        response_xml = f'<ret><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe><nProt>12345</nProt></infProt></protNFe></ret>'
        self.service.store_document(
            access_key=key, model="55", environment="PRODUCAO", request_xml=request,
            response=FiscalResponse(True, "100", "Autorizado", "12345", access_key=key, raw_xml=response_xml),
            actor="admin",
        )
        event_xml, _ = self.service.build_event_xml(
            event_type="CCE", access_key=key, sequence=1, actor_document="12345678000195",
            correction="Corrigir informação complementar para teste.", environment="PRODUCAO",
        )
        self.service.register_event(
            access_key=key, event_type="CCE", request_xml=event_xml, actor="admin",
            response=FiscalResponse(True, "135", "Evento registrado", "EV123", raw_xml="<ret><cStat>135</cStat><nProt>EV123</nProt></ret>"),
        )
        output = Path(self.tmp.name) / "contabilidade.zip"
        result = self.service.export_accounting_package(
            start_date=now.date().isoformat(), end_date=now.date().isoformat(), output_path=output,
        )
        self.assertEqual((result["documents"], result["events"]), (1, 1))
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            self.assertIn(f"producao/NFe/NFe{key}.xml", names)
            self.assertTrue(any(name.endswith("_CCE_envio.xml") for name in names))
            manifest = json.loads(archive.read("manifesto.json"))
        self.assertEqual(manifest["documents"][0]["access_key"], key)
        self.assertFalse(manifest["includes_homologation"])

    def test_exportacao_contabil_exclui_homologacao_por_padrao(self):
        now = datetime.now().astimezone()
        key = self.service.build_access_key(
            state_code="29", issued_at=now, cnpj="12345678000195", model="65",
            series=1, number=78, emission_type=1, numeric_code="76543211",
        )
        request = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00"/></NFe>'
        response_xml = f'<ret><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe><nProt>12346</nProt></infProt></protNFe></ret>'
        self.service.store_document(
            access_key=key, model="65", environment="HOMOLOGACAO", request_xml=request,
            response=FiscalResponse(True, "100", "Autorizado", "12346", access_key=key, raw_xml=response_xml),
            actor="admin",
        )
        output = Path(self.tmp.name) / "somente_producao.zip"
        result = self.service.export_accounting_package(
            start_date=now.date().isoformat(), end_date=now.date().isoformat(), output_path=output,
        )
        self.assertEqual(result["documents"], 0)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), {"LEIA-ME.txt", "manifesto.json"})

    def test_exportacao_contabil_inclui_cancelada_e_entrada_dfe_pela_data_do_xml(self):
        issued = datetime.now().astimezone().replace(day=3)
        key = self.service.build_access_key(
            state_code="29", issued_at=issued, cnpj="12345678000195", model="55",
            series=1, number=79, emission_type=1, numeric_code="76543213",
        )
        request = (
            f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00">'
            f'<ide><mod>55</mod><dhEmi>{issued.isoformat()}</dhEmi></ide></infNFe></NFe>'
        )
        response_xml = f'<ret><protNFe><infProt><cStat>100</cStat><chNFe>{key}</chNFe><nProt>12347</nProt></infProt></protNFe></ret>'
        self.service.store_document(
            access_key=key, model="55", environment="PRODUCAO", request_xml=request,
            response=FiscalResponse(True, "100", "Autorizado", "12347", access_key=key, raw_xml=response_xml),
            actor="admin",
        )
        self.service._mark_document_cancelled(
            access_key=key, event_protocol="CANCEL123", actor="admin",
            event_record={"status_code": "135", "message": "Cancelamento homologado"},
        )
        received_key = "29" + "8" * 42
        received_xml = (
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe>'
            f'<ide><dhEmi>{issued.isoformat()}</dhEmi></ide></infNFe></NFe>'
            f'<protNFe><infProt><chNFe>{received_key}</chNFe></infProt></protNFe></nfeProc>'
        ).encode()
        received_path = Path(self.tmp.name) / "entrada.xml"
        received_path.write_bytes(received_xml)
        output = Path(self.tmp.name) / "contabilidade_completa.zip"

        result = self.service.export_accounting_package(
            start_date=issued.date().isoformat(), end_date=issued.date().isoformat(),
            output_path=output,
            received_documents=[{
                "nsu": "1", "access_key": received_key, "schema": "procNFe_v4.00.xsd",
                "issued_at": issued.isoformat(), "path": str(received_path),
                "sha256": hashlib.sha256(received_xml).hexdigest(),
            }],
        )

        self.assertEqual(result["documents"], 1)
        self.assertEqual(result["received_documents"], 1)
        self.assertEqual(result["received_summaries"], 0)
        with zipfile.ZipFile(output) as archive:
            manifest = json.loads(archive.read("manifesto.json"))
            self.assertEqual(manifest["documents"][0]["status"], "CANCELADO")
            self.assertEqual(manifest["received_documents"][0]["access_key"], received_key)
            self.assertEqual(manifest["received_documents"][0]["content"], "XML_COMPLETO")
            self.assertTrue(any(name.startswith("entradas_DFe/") for name in archive.namelist()))

        validation = self.service.validate_accounting_package(output)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["files_checked"], 2)

    def test_validacao_do_pacote_contabil_rejeita_xml_alterado(self):
        package = Path(self.tmp.name) / "alterado.zip"
        manifest = {
            "product": "NabiCode", "version": 1,
            "period": {"start": "2026-08-01", "end": "2026-08-31"},
            "documents": [{"file": "producao/NFe/nota.xml", "sha256": "0" * 64}],
            "received_documents": [], "events": [],
        }
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("producao/NFe/nota.xml", b"<xml/>")
            archive.writestr("manifesto.json", json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "alterado ou corrompido"):
            self.service.validate_accounting_package(package)

    def test_relatorio_fiscal_csv_deriva_valores_do_xml_e_inutilizacoes(self):
        now = datetime.now().astimezone()
        key = self.service.build_access_key(
            state_code="29", issued_at=now, cnpj="12345678000195", model="55",
            series=2, number=81, emission_type=1, numeric_code="76543212",
        )
        request = f"""<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00">
          <ide><mod>55</mod><serie>2</serie><nNF>81</nNF><dhEmi>{now.isoformat()}</dhEmi></ide>
          <dest><CNPJ>98765432000198</CNPJ></dest><total><ICMSTot>
          <vBC>100.00</vBC><vICMS>18.00</vICMS><vIPI>5.00</vIPI><vPIS>1.65</vPIS>
          <vCOFINS>7.60</vCOFINS><vNF>125.00</vNF></ICMSTot>
          <IBSCBSTot><vIBS>0.10</vIBS><vCBS>0.90</vCBS></IBSCBSTot></total>
        </infNFe></NFe>"""
        response_xml = f"<ret><protNFe><infProt><cStat>100</cStat><chNFe>{key}</chNFe><nProt>12381</nProt></infProt></protNFe></ret>"
        self.service.store_document(
            access_key=key, model="55", environment="PRODUCAO", request_xml=request,
            response=FiscalResponse(True, "100", "Autorizado", "12381", access_key=key, raw_xml=response_xml),
            actor="admin",
        )
        self.service.register_event(
            access_key="0" * 44, event_type="INUTILIZACAO", actor="admin",
            request_xml="<inutNFe><infInut><tpAmb>1</tpAmb></infInut></inutNFe>",
            response=FiscalResponse(True, "102", "Inutilizacao homologada", "", raw_xml="<ret><cStat>102</cStat></ret>"),
            metadata={
                "environment": "PRODUCAO", "model": "55", "series": 2,
                "start_number": 82, "end_number": 84, "year": now.year,
            },
        )
        output = Path(self.tmp.name) / "relatorio.csv"
        result = self.service.export_fiscal_report_csv(
            start_date=now.date().isoformat(), end_date=now.date().isoformat(), output_path=output,
        )
        self.assertEqual(result["rows"], 2)
        with output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter=";"))
        self.assertEqual(rows[0]["numero"], "81")
        self.assertEqual(rows[0]["valor_bruto"], "125.00")
        self.assertEqual(rows[0]["valor_icms"], "18.00")
        self.assertEqual(rows[1]["status"], "INUTILIZADO")
        self.assertEqual(rows[1]["numero"], "82-84")

    def test_registra_evento_e_gera_espelho_fiscal_apenas_para_autorizada(self):
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
        pdf = self.service.generate_fiscal_mirror_pdf(authorized_xml=proc, output_path=Path(self.tmp.name) / "espelho.pdf")
        self.assertTrue(pdf.is_file())
        self.assertGreater(pdf.stat().st_size, 500)
        with self.assertRaises(ValueError):
            self.service.generate_fiscal_mirror_pdf(authorized_xml="<NFe/>", output_path=Path(self.tmp.name) / "invalido.pdf")

    def test_gera_danfe_oficial_modelo_55_com_xml_assinado_e_autorizado(self):
        xml, key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "trade_name": "EMPRESA",
                "city_code": "2927408", "city": "SALVADOR", "state": "BA",
                "street": "RUA TESTE", "number": "100", "district": "CENTRO",
                "zip_code": "40000000", "state_registration": "123456789",
                "tax_regime_code": 1,
            },
            recipient={
                "document": "98765432000198", "name": "CLIENTE TESTE",
                "street": "AVENIDA CLIENTE", "number": "20", "district": "COMERCIO",
                "city_code": "2927408", "city": "SALVADOR", "state": "BA",
                "zip_code": "40010000", "state_taxpayer_indicator": 9,
            },
            items=[{
                "code": "P1", "description": "PRODUTO TESTE", "quantity": 1,
                "unit_price": 10, "ncm": "94036000", "cfop": "5102", "unit": "UN",
            }],
            document={
                "model": "55", "series": 1, "number": 91, "state_code": "29",
                "environment": "HOMOLOGACAO", "numeric_code": "87654321",
            },
        )
        signed = self.service.sign_xml(
            xml, reference_id=f"NFe{key}", pfx_path=self.pfx_path, password=self.password,
        )
        response = (
            '<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><protNFe versao="4.00"><infProt>'
            f'<tpAmb>2</tpAmb><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe>'
            '<nProt>123456789012345</nProt></infProt></protNFe></retEnviNFe>'
        )
        processed = self.service.merge_authorization_protocol(signed, response)
        output = self.service.generate_official_danfe_pdf(
            authorized_xml=processed, output_path=Path(self.tmp.name) / "danfe-oficial.pdf",
        )
        self.assertEqual(output.read_bytes()[:5], b"%PDF-")
        self.assertGreater(output.stat().st_size, 3_000)

    def test_danfe_oficial_rejeita_modelo_65(self):
        with patch.object(
            self.service, "validate_authorized_xml", return_value={"model": "65"}
        ), self.assertRaisesRegex(ValueError, "somente NF-e modelo 55"):
            self.service.generate_official_danfe_pdf(
                authorized_xml=b"<xml/>", output_path=Path(self.tmp.name) / "nfce.pdf",
            )

    def test_gera_danfe_nfce_80mm_autorizada_com_qrcode(self):
        xml, key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2927408",
                "city": "SALVADOR", "state": "BA", "street": "RUA TESTE", "number": "100",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={},
            items=[{
                "code": "P1", "description": "PRODUTO TESTE", "quantity": 2,
                "unit_price": 5, "ncm": "94036000", "cfop": "5102", "unit": "UN",
            }],
            document={
                "model": "65", "series": 1, "number": 92, "state_code": "29",
                "environment": "HOMOLOGACAO", "numeric_code": "87654322",
            },
        )
        signed = self.service.sign_xml(
            xml, reference_id=f"NFe{key}", pfx_path=self.pfx_path, password=self.password,
        )
        response = (
            '<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><protNFe versao="4.00"><infProt>'
            f'<tpAmb>2</tpAmb><cStat>100</cStat><xMotivo>Autorizado</xMotivo><chNFe>{key}</chNFe>'
            '<nProt>123456789012346</nProt></infProt></protNFe></retEnviNFe>'
        )
        processed = self.service.merge_authorization_protocol(signed, response)
        output = self.service.generate_nfce_auxiliary_pdf(
            fiscal_xml=processed, output_path=Path(self.tmp.name) / "danfe-nfce.pdf",
        )
        self.assertEqual(output.read_bytes()[:5], b"%PDF-")
        self.assertGreater(output.stat().st_size, 2_000)

    def test_danfe_nfce_bloqueia_rascunho_normal_sem_autorizacao(self):
        with self.assertRaisesRegex(ValueError, "chave de acesso"):
            self.service.generate_nfce_auxiliary_pdf(
                fiscal_xml="<NFe><infNFe><ide><mod>65</mod><tpEmis>1</tpEmis></ide></infNFe></NFe>",
                output_path=Path(self.tmp.name) / "rascunho.pdf",
            )

    def test_gera_danfe_nfce_de_contingencia_offline_assinada(self):
        xml, _key = self.service.build_document_xml(
            issuer={
                "cnpj": "12345678000195", "name": "EMPRESA TESTE", "city_code": "2927408",
                "city": "SALVADOR", "state": "BA", "street": "RUA TESTE", "number": "100",
                "district": "CENTRO", "zip_code": "40000000", "state_registration": "123",
                "tax_regime_code": 1,
            },
            recipient={},
            items=[{
                "code": "P1", "description": "PRODUTO TESTE", "quantity": 1,
                "unit_price": 10, "ncm": "94036000", "cfop": "5102", "unit": "UN",
            }],
            document={
                "model": "65", "series": 1, "number": 93, "state_code": "29",
                "environment": "HOMOLOGACAO", "numeric_code": "87654323",
            },
        )
        contingency = self.service.apply_contingency(
            xml, reason="Internet indisponível durante a venda.", emission_type=9,
        )
        key = self.service._extract_access_key_from_xml(contingency)
        with_qr = self.service.add_nfce_qr_code_v3(
            contingency, pfx_path=self.pfx_path, password=self.password,
        )
        signed = self.service.sign_xml(
            with_qr, reference_id=f"NFe{key}", pfx_path=self.pfx_path, password=self.password,
        )
        output = self.service.generate_nfce_auxiliary_pdf(
            fiscal_xml=signed, output_path=Path(self.tmp.name) / "danfe-contingencia.pdf",
        )
        self.assertEqual(output.read_bytes()[:5], b"%PDF-")
        self.assertGreater(output.stat().st_size, 2_000)


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

    def test_fila_de_contingencia_controla_prazo_de_24_horas(self):
        key = "29" + "0" * 18 + "65" + "0" * 12 + "9" + "0" * 9
        xml = (
            '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
            f'<infNFe Id="NFe{key}"><ide><mod>65</mod><tpEmis>9</tpEmis></ide></infNFe></NFe>'
        )
        queued = self.service.enqueue_transmission(
            operation="autorizacao", xml=xml, actor="caixa", model="65", access_key=key,
        )
        created = datetime.fromisoformat(queued["created_at"])
        deadline = datetime.fromisoformat(queued["contingency_deadline_at"])
        self.assertTrue(queued["contingency"])
        self.assertEqual(deadline - created, timedelta(hours=24))

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

    def test_fila_nao_contorna_bloqueio_de_producao(self):
        self.service.save_config({
            "enabled": True, "environment": "PRODUCAO", "cnpj": "12345678000195",
            "state": "BA", "tax_regime": "SIMPLES", "certificate_path": str(self.pfx_path),
            "endpoints": {"HOMOLOGACAO": {}, "PRODUCAO": {"autorizacao": "https://sefaz.invalid/aut"}},
        })
        key = "29" + "0" * 18 + "65" + "0" * 22
        xml = f'<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}"/></NFe></enviNFe>'
        self.service.enqueue_transmission(
            operation="autorizacao", xml=xml, actor="admin", model="65", max_attempts=1
        )
        called = []
        original = self.service.transmit
        self.service.transmit = lambda **kwargs: called.append(kwargs)
        try:
            processed = self.service.process_transmission_queue(password=self.password)
        finally:
            self.service.transmit = original
        self.assertEqual(processed[0]["status"], "FALHA")
        self.assertIn("produção bloqueada", processed[0]["last_error"])
        self.assertEqual(called, [])

    def test_fila_nao_transmite_venda_cancelada_localmente(self):
        self.service.save_config({
            "enabled": True, "environment": "HOMOLOGACAO", "cnpj": "12345678000195",
            "state": "BA", "tax_regime": "SIMPLES", "certificate_path": str(self.pfx_path),
        })
        key = "29" + "3" * 18 + "65" + "4" * 22
        connection = self.service.connection_factory()
        connection.execute("CREATE TABLE fiscal_sale_documents(access_key TEXT,status TEXT)")
        connection.execute("INSERT INTO fiscal_sale_documents VALUES(?, 'CANCELADO_LOCAL')", (key,))
        connection.commit(); connection.close()
        xml = f'<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}"/></NFe></enviNFe>'
        self.service.enqueue_transmission(operation="autorizacao", xml=xml, actor="admin", model="65")
        called = []
        original = self.service.transmit
        self.service.transmit = lambda **kwargs: called.append(kwargs)
        try:
            processed = self.service.process_transmission_queue(password=self.password)
        finally:
            self.service.transmit = original
        self.assertEqual(processed[0]["status"], "CANCELADO")
        self.assertEqual(called, [])

    def test_fila_cancelada_nao_pode_ser_reativada(self):
        key = "29" + "1" * 42
        xml = f'<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}"/></NFe></enviNFe>'
        item = self.service.enqueue_transmission(
            operation="autorizacao", xml=xml, actor="admin", model="65"
        )
        self.service.cancel_transmission(item["id"], actor="admin", reason="Venda cancelada")

        with self.assertRaisesRegex(ValueError, "cancelada"):
            self.service.retry_transmission(item["id"], actor="admin")

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
        forced = self.service.force_receipt_check(second["id"], actor="gerente")
        self.assertEqual(forced["operation"], "recibo")
        self.assertEqual(forced["receipt_check_requested_by"], "gerente")
        self.assertLessEqual(datetime.fromisoformat(forced["next_attempt_at"]), datetime.now(timezone.utc))

    def test_consulta_forcada_nao_reenvia_autorizacao_sem_recibo(self):
        item = self.service.enqueue_transmission(
            operation="autorizacao", xml=f'<NFe><infNFe Id="NFe{"7" * 44}"/></NFe>',
            access_key="7" * 44, actor="admin",
        )
        with self.assertRaisesRegex(ValueError, "ainda não possui recibo"):
            self.service.force_receipt_check(item["id"], actor="admin")

    def test_retransmissao_em_lote_seleciona_apenas_nfce_em_contingencia(self):
        contingency_key = "2" * 34 + "9" + "2" * 9
        normal_key = "3" * 44
        contingency = self.service.enqueue_transmission(
            operation="autorizacao",
            xml=f'<NFe><infNFe Id="NFe{contingency_key}"><ide><mod>65</mod><tpEmis>9</tpEmis></ide></infNFe></NFe>',
            access_key=contingency_key, model="65", actor="caixa",
        )
        self.service.enqueue_transmission(
            operation="autorizacao",
            xml=f'<NFe><infNFe Id="NFe{normal_key}"><ide><mod>65</mod><tpEmis>1</tpEmis></ide></infNFe></NFe>',
            access_key=normal_key, model="65", actor="caixa",
        )
        result = self.service.retry_contingency_batch(actor="gerente")
        self.assertEqual(result["scheduled"], 1)
        self.assertEqual(result["queue_ids"], [contingency["id"]])
        queued = {row["id"]: row for row in self.service.list_transmission_queue()}
        self.assertTrue(queued[contingency["id"]]["contingency"])
        self.assertEqual(queued[contingency["id"]]["contingency_batch_requested_by"], "gerente")

    def test_processamento_por_ids_nao_transmite_outros_pendentes(self):
        first = self.service.enqueue_transmission(
            operation="consulta", xml="<consSitNFe/>", actor="admin"
        )
        second = self.service.enqueue_transmission(
            operation="consulta", xml="<consSitNFe><xServ>CONSULTAR</xServ></consSitNFe>", actor="admin"
        )
        original = self.service.transmit
        self.service.transmit = lambda **_: FiscalResponse(True, "100", "Consulta concluída", raw_xml="<ret/>")
        try:
            processed = self.service.process_transmission_queue(
                password=self.password, queue_ids=[second["id"]]
            )
        finally:
            self.service.transmit = original
        self.assertEqual([row["id"] for row in processed], [second["id"]])
        queued = {row["id"]: row for row in self.service.list_transmission_queue()}
        self.assertEqual(queued[first["id"]]["status"], "PENDENTE")

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
        unsigned = f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00"><ide><mod>55</mod></ide><dest><email>cliente@example.com</email></dest></infNFe></NFe>'
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

    def test_email_do_destinatario_so_e_lido_de_xml_autorizado_valido(self):
        _key, processed = self._authorized_signed_xml()
        self.assertEqual(
            self.service.authorized_recipient_email(processed), "cliente@example.com"
        )

    def test_duplica_autorizada_para_pre_venda_com_cadastro_atual_sem_identidade_fiscal(self):
        conn = self.connect()
        conn.execute(
            "CREATE TABLE produtos(id INTEGER PRIMARY KEY,codigo TEXT,nome TEXT,preco_venda REAL,ativo INTEGER,controla_estoque INTEGER)"
        )
        conn.execute("CREATE TABLE clientes(id INTEGER PRIMARY KEY,nome TEXT,cpf TEXT)")
        conn.execute("INSERT INTO produtos VALUES(7,'P1','PRODUTO ATUAL',25.50,1,1)")
        conn.execute("INSERT INTO clientes VALUES(9,'CLIENTE ATUAL','98765432000198')")
        conn.commit(); conn.close()
        key = self.service.build_access_key(
            state_code="29", issued_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            cnpj="12345678000195", model="55", series=1, number=400,
            emission_type=1, numeric_code="12344321",
        )
        unsigned = (
            f'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00">'
            '<ide><mod>55</mod></ide><dest><CNPJ>98765432000198</CNPJ><xNome>CLIENTE ANTIGO</xNome></dest>'
            '<det nItem="1"><prod><cProd>P1</cProd><qCom>2.0000</qCom><vUnCom>10.00</vUnCom></prod></det>'
            '</infNFe></NFe>'
        )
        signed = self.service.sign_xml(
            unsigned, reference_id=f"NFe{key}", pfx_path=self.pfx_path, password=self.password
        )
        response = (
            '<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><protNFe versao="4.00"><infProt>'
            f'<tpAmb>2</tpAmb><cStat>100</cStat><chNFe>{key}</chNFe><nProt>123456789012345</nProt>'
            '</infProt></protNFe></retEnviNFe>'
        )
        processed = self.service.merge_authorization_protocol(signed, response)
        self.service.import_authorized_xml(processed, actor="admin")
        pdv = PDVService(self.connect)
        draft = self.service.duplicate_authorized_to_pdv_draft(
            access_key=key, pdv_service=pdv
        )
        self.assertEqual(draft.cliente_id, 9)
        self.assertEqual(draft.itens[0]["produto_id"], 7)
        self.assertEqual(draft.itens[0]["preco"], Decimal("25.50"))
        self.assertNotIn("protocol", draft.itens[0])
        with self.assertRaisesRegex(ValueError, "já possui uma pré-venda"):
            self.service.duplicate_authorized_to_pdv_draft(access_key=key, pdv_service=pdv)

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
