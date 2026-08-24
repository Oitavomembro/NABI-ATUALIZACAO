import base64
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from services.fiscal_outbox_service import FiscalOutboxService
from services.fiscal_sale_service import FiscalSaleDraft, FiscalSaleService


class FiscalOutboxServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "outbox.db"
        connection = sqlite3.connect(self.db)
        connection.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT);
            CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,tipo TEXT);
            CREATE TABLE fiscal_sale_documents(
                id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER NOT NULL UNIQUE,
                reservation_id TEXT NOT NULL UNIQUE,access_key TEXT NOT NULL UNIQUE,
                model TEXT NOT NULL,environment TEXT NOT NULL,status TEXT NOT NULL,
                xml_b64 TEXT NOT NULL,queue_id TEXT NOT NULL DEFAULT '',protocol TEXT DEFAULT '',
                last_error TEXT DEFAULT '',created_at TEXT,updated_at TEXT);
        """)
        FiscalOutboxService.ensure_schema(connection)
        connection.commit(); connection.close()
        self.factory = lambda: sqlite3.connect(self.db, timeout=2)
        self.service = FiscalOutboxService(self.factory)
        self.sale_service = FiscalSaleService(SimpleNamespace(
            require_authenticated_actor=lambda action, operation: "caixa"
        ))

    def tearDown(self):
        self.temp.cleanup()

    def _document(self, *, key="29" + "1" * 42, sale_id=None):
        connection = self.factory()
        if sale_id is None:
            sale_id = connection.execute("INSERT INTO movimentacoes(tipo) VALUES('COMPRA')").lastrowid
        now = datetime.now(timezone.utc).isoformat()
        document_id = connection.execute(
            """INSERT INTO fiscal_sale_documents
               (sale_id,reservation_id,access_key,model,environment,status,xml_b64,created_at,updated_at)
               VALUES(?,?,?,?,?,'PENDENTE',?,?,?)""",
            (sale_id, f"R-{sale_id}", key, "65", "HOMOLOGACAO", base64.b64encode(b"<NFe/>").decode(), now, now),
        ).lastrowid
        connection.commit(); connection.close()
        return sale_id, document_id

    def _enqueue(self, *, key="29" + "1" * 42):
        sale_id, document_id = self._document(key=key)
        connection = self.factory()
        connection.execute("BEGIN IMMEDIATE")
        result = self.service.enqueue_in_transaction(
            connection, sale_id=sale_id, fiscal_document_id=document_id,
            access_key=key, environment="HOMOLOGACAO", operation="autorizacao",
            model="65", reservation_id=f"R-{sale_id}", xml_b64=base64.b64encode(b"<NFe/>").decode(),
            actor="caixa",
        )
        connection.commit(); connection.close()
        return result

    def test_venda_fiscal_cria_exatamente_um_documento_e_item(self):
        sale_id = 1
        connection = self.factory()
        connection.execute("INSERT INTO movimentacoes(id,tipo) VALUES(1,'COMPRA')")
        draft = FiscalSaleDraft("R-1", "29" + "1" * 42, "65", "HOMOLOGACAO", b"<NFe/>")
        self.sale_service.persist_draft(connection, sale_id, draft)
        connection.commit()
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM fiscal_sale_documents").fetchone()[0], 1)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM fiscal_outbox").fetchone()[0], 1)
        connection.close()

    def test_falha_na_outbox_reverte_documento_e_venda(self):
        connection = self.factory()
        connection.execute("""CREATE TRIGGER fail_outbox BEFORE INSERT ON fiscal_outbox
                              BEGIN SELECT RAISE(ABORT,'falha outbox'); END""")
        connection.commit(); connection.execute("BEGIN")
        sale_id = connection.execute("INSERT INTO movimentacoes(tipo) VALUES('COMPRA')").lastrowid
        draft = FiscalSaleDraft("R-X", "29" + "2" * 42, "65", "HOMOLOGACAO", b"<NFe/>")
        with self.assertRaises(sqlite3.IntegrityError):
            self.sale_service.persist_draft(connection, sale_id, draft)
        connection.rollback()
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM fiscal_sale_documents").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM fiscal_outbox").fetchone()[0], 0)
        connection.close()

    def test_mesmo_documento_nao_cria_dois_itens(self):
        item = self._enqueue()
        connection = self.factory(); connection.execute("BEGIN IMMEDIATE")
        duplicate = self.service.enqueue_in_transaction(
            connection, sale_id=1, fiscal_document_id=1, access_key="29" + "1" * 42,
            environment="HOMOLOGACAO", operation="autorizacao", model="65",
            reservation_id="R-1", xml_b64=base64.b64encode(b"<NFe/>").decode(), actor="caixa")
        connection.commit(); connection.close()
        self.assertEqual(item["id"], duplicate["id"])
        self.assertEqual(len(self.service.list_items()), 1)

    def test_mesma_chave_nao_cria_itens_incompativeis(self):
        self._enqueue()
        sale_id, document_id = self._document(key="29" + "2" * 42)
        connection = self.factory(); connection.execute("BEGIN IMMEDIATE")
        with self.assertRaises(RuntimeError):
            self.service.enqueue_in_transaction(
                connection, sale_id=sale_id, fiscal_document_id=document_id,
                access_key="29" + "1" * 42, environment="HOMOLOGACAO",
                operation="autorizacao", model="65", reservation_id=f"R-{sale_id}",
                xml_b64="WA==", actor="caixa")
        connection.rollback(); connection.close()

    def test_claim_e_lease_impedem_segundo_worker(self):
        self._enqueue()
        now = datetime.now(timezone.utc) + timedelta(seconds=1)
        first = self.service.claim_next(worker_id="w1", lease_seconds=60, now=now)
        second = self.service.claim_next(worker_id="w2", lease_seconds=60, now=now)
        self.assertIsNotNone(first); self.assertIsNone(second)

    def test_lease_vencido_permite_recuperacao(self):
        self._enqueue(); now = datetime.now(timezone.utc) + timedelta(seconds=1)
        self.service.claim_next(worker_id="w1", lease_seconds=1, now=now)
        recovered = self.service.claim_next(worker_id="w2", lease_seconds=60, now=now + timedelta(seconds=2))
        self.assertEqual(recovered["worker_id"], "w2")

    def test_lease_vencido_apos_inicio_de_transmissao_nao_e_reivindicado(self):
        self._enqueue(); now = datetime.now(timezone.utc) + timedelta(seconds=1)
        claimed = self.service.claim_next(worker_id="w1", lease_seconds=1, now=now)
        rows = self.service.list_items()
        rows[0]["transmission_started_at"] = now.isoformat()
        self.service.save_records(rows)
        recovered = self.service.claim_next(
            worker_id="w2", lease_seconds=60, now=now + timedelta(seconds=2)
        )
        self.assertIsNone(recovered)
        self.assertEqual(self.service.list_items()[0]["status"], "RESPOSTA_DESCONHECIDA")

    def test_concluido_nao_e_reivindicado_novamente(self):
        self._enqueue(); claimed = self.service.claim_next(worker_id="w1")
        self.service.complete(int(claimed["id"]), worker_id="w1", receipt="123")
        self.assertIsNone(self.service.claim_next(worker_id="w2"))

    def test_resposta_desconhecida_nao_volta_automaticamente(self):
        self._enqueue(); claimed = self.service.claim_next(worker_id="w1")
        self.service.mark_unknown(int(claimed["id"]), worker_id="w1", error_message="timeout")
        self.assertIsNone(self.service.claim_next(worker_id="w2", now=datetime.now(timezone.utc) + timedelta(days=1)))
        self.assertEqual(self.service.list_items()[0]["status"], "RESPOSTA_DESCONHECIDA")

    def test_migracao_da_fila_json_preserva_origem_e_nao_duplica(self):
        sale_id, _document_id = self._document()
        legacy = [{"id": "LEG-1", "operation": "autorizacao", "access_key": "29" + "1" * 42,
                   "model": "65", "status": "PENDENTE", "xml_b64": "WA==", "actor": "caixa"}]
        connection = self.factory()
        connection.execute("INSERT INTO configuracoes VALUES(?,?)", (self.service.LEGACY_KEY, json.dumps(legacy)))
        connection.commit(); connection.close()
        first = self.service.migrate_legacy(); second = self.service.migrate_legacy()
        self.assertEqual(first["migrated"], 1); self.assertEqual(second["migrated"], 0)
        self.assertEqual(len(self.service.list_items()), 1)
        connection = self.factory()
        self.assertEqual(json.loads(connection.execute("SELECT valor FROM configuracoes WHERE chave=?", (self.service.LEGACY_KEY,)).fetchone()[0]), legacy)
        connection.close()

    def test_pendencia_permanece_apos_modo_comercial(self):
        self._enqueue()
        connection = self.factory()
        connection.execute("INSERT OR REPLACE INTO configuracoes VALUES('modo_operacao','COMERCIAL')")
        connection.commit(); connection.close()
        self.assertEqual(len(self.service.list_items()), 1)


if __name__ == "__main__":
    unittest.main()
