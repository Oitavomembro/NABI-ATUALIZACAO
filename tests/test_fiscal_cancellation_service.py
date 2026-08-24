from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.fiscal_cancellation_service import FiscalCancellationService


class FakeFiscal:
    STATE_CODES = {"BA": "29"}

    def __init__(self, database: Path, stored: dict):
        self.database = database
        self.stored = stored
        self.environment = "HOMOLOGACAO"
        self.network_calls = 0

    def connection_factory(self):
        return sqlite3.connect(self.database)

    @staticmethod
    def _normalize_access_key(value):
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    def list_documents(self):
        return [dict(self.stored)] if self.stored else []

    def verify_document_integrity(self, **_kwargs):
        return {"valid": bool(self.stored.get("integrity", True))}

    def load_config(self):
        return {
            "environment": self.environment,
            "cnpj": "12345678000195",
            "certificate_path": "certificado-teste.pfx",
        }

    def validate_event_eligibility(self, **_kwargs):
        return dict(self.stored)

    def build_event_xml(self, *, access_key, **_kwargs):
        return f"<evento><chNFe>{access_key}</chNFe></evento>".encode(), "ID110111TESTE"

    def sign_xml(self, xml, **_kwargs):
        return bytes(xml)

    def _event_envelope(self, xml):
        return bytes(xml)

    def validate_official_xml(self, *_args, **_kwargs):
        return None


class FiscalCancellationServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.database = self.folder / "cancel.db"
        self.xml = self.folder / "autorizado.xml"
        self.key65 = "29260812345678000195650010000000011123456780"
        self.authorized_at = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
        self.write_authorized_xml(self.authorized_at.isoformat())
        self.stored = {
            "access_key": self.key65, "model": "65", "environment": "HOMOLOGACAO",
            "status": "AUTORIZADO", "protocol": "123456789012345",
            "created_at": self.authorized_at.isoformat(),
            "request_path": str(self.xml), "response_path": str(self.xml),
            "processed_path": str(self.xml),
            "request_sha256": hashlib.sha256(self.xml.read_bytes()).hexdigest(),
            "response_sha256": hashlib.sha256(self.xml.read_bytes()).hexdigest(),
            "processed_sha256": hashlib.sha256(self.xml.read_bytes()).hexdigest(),
        }
        connection = sqlite3.connect(self.database)
        connection.executescript("""
            CREATE TABLE movimentacoes(
                id INTEGER PRIMARY KEY,tipo TEXT,status_pagamento TEXT,data TEXT,valor REAL
            );
            INSERT INTO movimentacoes VALUES(1,'COMPRA','PAGO','2026-08-21T12:00:00',100);
            CREATE TABLE fiscal_sale_documents(
                id INTEGER PRIMARY KEY,sale_id INTEGER UNIQUE,reservation_id TEXT UNIQUE,
                access_key TEXT UNIQUE,model TEXT,environment TEXT,status TEXT,xml_b64 TEXT,
                queue_id TEXT DEFAULT '',protocol TEXT,last_error TEXT DEFAULT '',
                created_at TEXT,updated_at TEXT
            );
        """)
        connection.execute(
            "INSERT INTO fiscal_sale_documents VALUES(1,1,'R1',?,?,?,?,?,'','123456789012345','',?,?)",
            (self.key65, "65", "HOMOLOGACAO", "AUTORIZADO", "PHhtbC8+",
             self.authorized_at.isoformat(), self.authorized_at.isoformat()),
        )
        connection.commit(); connection.close()
        self.fiscal = FakeFiscal(self.database, self.stored)
        self.reversals = []
        self.service = FiscalCancellationService(
            self.fiscal,
            cancel_commercial_sale=lambda sale_id, actor: self.reversals.append((sale_id, actor)),
            actor_provider=lambda: "gerente",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def now(self, minutes=10):
        return self.authorized_at + timedelta(minutes=minutes)

    def write_authorized_xml(self, dh_recbto: str | None):
        received = f"<dhRecbto>{dh_recbto}</dhRecbto>" if dh_recbto is not None else ""
        self.xml.write_text(
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">'
            f'<protNFe><infProt><chNFe>{self.key65}</chNFe>{received}'
            '<nProt>123456789012345</nProt></infProt></protNFe></nfeProc>',
            encoding="utf-8",
        )

    def request(self, **overrides):
        data = dict(
            sale_id=1, password="senha",
            justification="Venda desfeita antes da saída.",
            no_circulation_confirmed=True, user_has_permission=True, now=self.now(),
        )
        data.update(overrides)
        return self.service.request(**data)

    def update_document(self, **values):
        connection = sqlite3.connect(self.database)
        for name, value in values.items():
            connection.execute(f"UPDATE fiscal_sale_documents SET {name}=? WHERE id=1", (value,))
        connection.commit(); connection.close()

    def test_nfce_ba_dentro_do_prazo_expoe_contador_timezone_e_dados(self):
        result = self.service.eligibility(1, user_has_permission=True, now=self.now(10))
        self.assertEqual(result["remaining_seconds"], 20 * 60)
        self.assertEqual(result["state"], "BA")
        self.assertEqual(result["model"], "65")
        self.assertEqual(result["authorized_at"], self.authorized_at.isoformat())

    def test_prazo_usa_dh_recbto_e_ignora_created_at_local(self):
        self.stored["created_at"] = (self.authorized_at + timedelta(days=90)).isoformat()
        self.update_document(
            created_at=(self.authorized_at - timedelta(days=90)).isoformat()
        )
        result = self.service.eligibility(1, user_has_permission=True, now=self.now(10))
        self.assertEqual(result["authorized_at"], self.authorized_at.isoformat())
        self.assertEqual(result["remaining_seconds"], 20 * 60)

    def test_dh_recbto_preserva_offset_no_calculo(self):
        self.write_authorized_xml("2026-08-21T09:00:00-03:00")
        result = self.service.eligibility(1, user_has_permission=True, now=self.now(10))
        self.assertEqual(result["authorized_at"], self.authorized_at.isoformat())
        self.assertEqual(result["remaining_seconds"], 20 * 60)

    def test_dh_recbto_ausente_bloqueia_sem_fallback(self):
        self.write_authorized_xml(None)
        with self.assertRaisesRegex(ValueError, "dhRecbto ausente ou inválido"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_dh_recbto_invalido_bloqueia_sem_fallback(self):
        self.write_authorized_xml("horario-invalido")
        with self.assertRaisesRegex(ValueError, "dhRecbto ausente ou inválido"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_dh_recbto_sem_offset_bloqueia(self):
        self.write_authorized_xml("2026-08-21T12:00:00")
        with self.assertRaisesRegex(ValueError, "timezone/offset"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_nfce_limites_de_trinta_minutos(self):
        before = self.service.eligibility(
            1, user_has_permission=True,
            now=self.authorized_at + timedelta(minutes=30) - timedelta(microseconds=1),
        )
        self.assertEqual(before["remaining_seconds"], 0)
        for moment in (
            self.authorized_at + timedelta(minutes=30),
            self.authorized_at + timedelta(minutes=30, microseconds=1),
        ):
            with self.assertRaisesRegex(ValueError, "Prazo normal"):
                self.service.eligibility(1, user_has_permission=True, now=moment)

    def test_nfce_ba_fora_do_prazo(self):
        with self.assertRaisesRegex(ValueError, "Prazo normal"):
            self.service.eligibility(1, user_has_permission=True, now=self.now(31))

    def test_nfe_usa_regra_independente_de_24_horas(self):
        key55 = self.key65[:20] + "55" + self.key65[22:]
        self.update_document(access_key=key55, model="55")
        self.stored.update(access_key=key55, model="55")
        result = self.service.eligibility(
            1, user_has_permission=True, now=self.authorized_at + timedelta(hours=23)
        )
        self.assertEqual(result["remaining_seconds"], 3600)
        with self.assertRaisesRegex(ValueError, "Prazo normal"):
            self.service.eligibility(
                1, user_has_permission=True,
                now=self.authorized_at + timedelta(hours=24, microseconds=1),
            )

    def test_uf_sem_regra_versionada_nao_inventa_prazo(self):
        key = "35" + self.key65[2:]
        self.update_document(access_key=key)
        self.stored["access_key"] = key
        with self.assertRaisesRegex(ValueError, "não versionada"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_documento_nao_autorizado(self):
        self.update_document(status="PENDENTE")
        with self.assertRaisesRegex(ValueError, "AUTORIZADO"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_xml_ausente(self):
        self.xml.unlink()
        with self.assertRaisesRegex(ValueError, "XML autorizado original"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_xml_com_integridade_invalida(self):
        self.stored["integrity"] = False
        with self.assertRaisesRegex(ValueError, "integridade"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_protocolo_ausente(self):
        self.update_document(protocol="")
        with self.assertRaisesRegex(ValueError, "Protocolo"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_chave_invalida(self):
        self.update_document(access_key="123")
        with self.assertRaisesRegex(ValueError, "Chave"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_usuario_sem_permissao(self):
        with self.assertRaises(PermissionError):
            self.service.eligibility(1, user_has_permission=False, now=self.now())

    def test_confirmacao_de_nao_circulacao_obrigatoria(self):
        with self.assertRaisesRegex(ValueError, "não circulou"):
            self.request(no_circulation_confirmed=False)

    def test_justificativa_entre_15_e_255(self):
        with self.assertRaisesRegex(ValueError, "15 e 255"):
            self.request(justification="curta")
        with self.assertRaisesRegex(ValueError, "15 e 255"):
            self.request(justification="x" * 256)

    def test_solicitacao_cria_um_evento_e_marca_pendente_sem_estorno(self):
        queued = self.request()
        self.assertEqual(queued["operation"], "evento")
        self.assertEqual(queued["event_type"], "CANCELAMENTO")
        self.assertTrue(queued["no_circulation_confirmed"])
        self.assertEqual(self.reversals, [])
        connection = sqlite3.connect(self.database)
        status = connection.execute("SELECT status FROM fiscal_sale_documents").fetchone()[0]
        connection.close()
        self.assertEqual(status, "CANCELAMENTO_PENDENTE")

    def test_clique_duplicado_nao_cria_segundo_evento(self):
        self.request()
        with self.assertRaisesRegex(ValueError, "pendente"):
            self.request()
        connection = sqlite3.connect(self.database)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM fiscal_outbox").fetchone()[0], 1)
        connection.close()

    def test_cancelamento_ja_pendente_e_ja_cancelado_sao_bloqueados(self):
        for status, message in (("CANCELAMENTO_PENDENTE", "pendente"), ("CANCELADO", "cancelado")):
            self.update_document(status=status)
            with self.assertRaisesRegex(ValueError, message):
                self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_resposta_desconhecida_bloqueia_novo_envio(self):
        self.update_document(status="RESPOSTA_DESCONHECIDA")
        with self.assertRaisesRegex(ValueError, "reconciliação"):
            self.service.eligibility(1, user_has_permission=True, now=self.now())

    def test_venda_comercial_nao_gera_evento_nem_rede(self):
        with self.assertRaisesRegex(ValueError, "COMERCIAL"):
            self.service.request(
                sale_id=999, password="",
                justification="Cancelamento comercial sem fiscal.",
                no_circulation_confirmed=True, user_has_permission=True, now=self.now(),
            )
        self.assertEqual(self.fiscal.network_calls, 0)

    def test_producao_bloqueada_antes_de_rede(self):
        self.update_document(environment="PRODUCAO")
        self.stored["environment"] = "PRODUCAO"
        with self.assertRaisesRegex(ValueError, "Produção fiscal"):
            self.request()
        self.assertEqual(self.fiscal.network_calls, 0)

    def test_aceite_dispara_estorno_somente_no_resultado_concluido(self):
        self.service.handle_worker_result({
            "event_type": "CANCELAMENTO", "status": "CONCLUIDO",
            "event_success": True, "sale_id": 1, "actor": "gerente",
        })
        self.assertEqual(self.reversals, [(1, "gerente")])
        self.reversals.clear()
        for status in ("FALHA", "RESPOSTA_DESCONHECIDA", "PROCESSANDO"):
            self.service.handle_worker_result({
                "event_type": "CANCELAMENTO", "status": status,
                "event_success": False, "sale_id": 1,
            })
        self.assertEqual(self.reversals, [])

    def test_falha_de_estorno_fica_explicita_para_recuperacao(self):
        service = FiscalCancellationService(
            self.fiscal,
            cancel_commercial_sale=lambda *_args: (_ for _ in ()).throw(RuntimeError("caixa ocupado")),
        )
        service.handle_worker_result({
            "event_type": "CANCELAMENTO", "status": "CONCLUIDO",
            "event_success": True, "sale_id": 1,
        })
        connection = sqlite3.connect(self.database)
        row = connection.execute(
            "SELECT status,last_error FROM fiscal_sale_documents WHERE id=1"
        ).fetchone(); connection.close()
        self.assertEqual(row[0], "FISCAL_CANCELADO_ESTORNO_PENDENTE")
        self.assertIn("caixa ocupado", row[1])

    def test_reinicio_recupera_estorno_pendente(self):
        self.update_document(status="FISCAL_CANCELADO_ESTORNO_PENDENTE")
        recovered = self.service.recover_pending_reversals()
        self.assertEqual(recovered, [1])
        self.assertEqual(self.reversals[0][0], 1)

    def test_xml_original_e_trilha_de_auditoria_ficam_na_outbox(self):
        original = self.xml.read_bytes()
        queued = self.request()
        self.assertEqual(self.xml.read_bytes(), original)
        self.assertEqual(queued["requested_by"], "gerente")
        self.assertEqual(queued["justification"], "Venda desfeita antes da saída.")
        self.assertTrue(queued["original_document_sha256"])

    def test_solicitacao_sem_provedor_de_sessao_falha_fechada(self):
        unauthenticated = FiscalCancellationService(self.fiscal)

        with self.assertRaisesRegex(PermissionError, "sessão autenticada"):
            unauthenticated.request(
                sale_id=1, password="senha",
                justification="Venda desfeita antes da saída.",
                no_circulation_confirmed=True, user_has_permission=True,
                now=self.now(),
            )

        connection = sqlite3.connect(self.database)
        status = connection.execute(
            "SELECT status FROM fiscal_sale_documents WHERE id=1"
        ).fetchone()[0]
        connection.close()
        self.assertEqual(status, "AUTORIZADO")

    def test_solicitacao_sem_identidade_na_sessao_falha_fechada(self):
        unauthenticated = FiscalCancellationService(
            self.fiscal, actor_provider=lambda: None
        )

        with self.assertRaisesRegex(PermissionError, "sessão autenticada"):
            unauthenticated.request(
                sale_id=1, password="senha",
                justification="Venda desfeita antes da saída.",
                no_circulation_confirmed=True, user_has_permission=True,
                now=self.now(),
            )

    def test_api_de_solicitacao_recusa_actor_livre(self):
        with self.assertRaisesRegex(TypeError, "unexpected keyword argument 'actor'"):
            self.service.request(
                sale_id=1, password="senha", actor="forjado",
                justification="Venda desfeita antes da saída.",
                no_circulation_confirmed=True, user_has_permission=True,
                now=self.now(),
            )

        connection = sqlite3.connect(self.database)
        try:
            status = connection.execute(
                "SELECT status FROM fiscal_sale_documents WHERE id=1"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(status, "AUTORIZADO")


if __name__ == "__main__":
    unittest.main()
