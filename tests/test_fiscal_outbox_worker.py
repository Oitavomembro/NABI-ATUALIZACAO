from __future__ import annotations

import base64
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.fiscal_outbox_service import FiscalOutboxService
from services.fiscal_outbox_worker import FiscalOutboxWorker
from services.fiscal_service import FiscalService


class FakeFiscalProcessor:
    def __init__(self, database: Path, *, password: str | None = "segredo") -> None:
        self.database = database
        self.password = password
        self.calls = 0
        self.reconciliations = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.block = False

    def connection_factory(self):
        return sqlite3.connect(self.database, timeout=2)

    def session_certificate_password(self):
        return self.password

    def _sync_sale_document(self, *_args, **_kwargs):
        return None

    def prepare_claimed_reconciliation(self, record, *, worker_id):
        self.reconciliations += 1
        target = dict(record)
        target["operation"] = "recibo" if target.get("receipt") else "consulta"
        target["reconciliation_for"] = "autorizacao"
        target["xml_b64"] = base64.b64encode(b"<consulta/>").decode("ascii")
        FiscalOutboxService(self.connection_factory).save_claimed_record(
            target, worker_id=worker_id, finish=False
        )
        return target

    def process_transmission_queue(self, *, queue_ids, claimed_worker_id, **_kwargs):
        self.calls += 1
        self.started.set()
        if self.block:
            self.release.wait(5)
        outbox = FiscalOutboxService(self.connection_factory)
        row = next(item for item in outbox.list_items() if item["id"] == str(queue_ids[0]))
        row["status"] = "CONCLUIDO"
        row["completed_at"] = datetime.now(timezone.utc).isoformat()
        outbox.save_claimed_record(row, worker_id=claimed_worker_id, finish=True)
        return [row]


class FiscalOutboxWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "worker.db"
        connection = sqlite3.connect(self.database)
        connection.execute("CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT)")
        connection.commit(); connection.close()
        self.processor = FakeFiscalProcessor(self.database)
        self.outbox = FiscalOutboxService(self.processor.connection_factory)

    def tearDown(self):
        self.temp.cleanup()

    def enqueue(self, *, operation="autorizacao", status="PENDENTE",
                environment="HOMOLOGACAO", receipt=""):
        connection = self.processor.connection_factory()
        connection.execute("BEGIN IMMEDIATE")
        row = self.outbox.enqueue_in_transaction(
            connection, sale_id=None, fiscal_document_id=None,
            access_key="29" + "1" * 42, environment=environment,
            operation=operation, model="65", reservation_id="R1",
            xml_b64=base64.b64encode(b"<NFe/>").decode("ascii"), actor="caixa",
        )
        connection.execute(
            "UPDATE fiscal_outbox SET status=?,receipt=? WHERE id=?",
            (status, receipt, int(row["id"])),
        )
        connection.commit(); connection.close()
        return self.outbox.list_items()[0]

    def worker(self, **kwargs):
        lease_seconds = kwargs.pop("lease_seconds", 60)
        return FiscalOutboxWorker(
            self.processor, poll_seconds=0.1, lease_seconds=lease_seconds,
            max_per_cycle=1, **kwargs,
        )

    def test_worker_inicia_e_encerra_sem_thread_orfa(self):
        worker = self.worker()
        self.assertTrue(worker.start())
        self.assertFalse(worker.start())
        self.assertTrue(worker.stop(timeout=2))
        self.assertFalse(worker.is_running)

    def test_inicio_nao_bloqueia_interface(self):
        worker = self.worker()
        started = time.monotonic(); worker.start(); elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.2)
        self.assertTrue(worker.stop(timeout=2))

    def test_sem_outbox_comercial_nao_processa_movimentacoes(self):
        connection = self.processor.connection_factory()
        connection.execute("CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY,tipo TEXT)")
        connection.execute("INSERT INTO movimentacoes VALUES(1,'COMPRA')")
        connection.commit(); connection.close()
        self.assertIsNone(self.worker().run_once())
        self.assertEqual(self.processor.calls, 0)

    def test_obrigacao_historica_processa_apos_modo_comercial(self):
        self.enqueue()
        connection = self.processor.connection_factory()
        connection.execute("INSERT INTO configuracoes VALUES('modo_operacao','COMERCIAL')")
        connection.commit(); connection.close()
        self.assertEqual(self.worker().run_once()["status"], "CONCLUIDO")

    def test_pendente_e_reivindicado_uma_vez(self):
        self.enqueue(); worker = self.worker()
        self.assertEqual(worker.run_once()["status"], "CONCLUIDO")
        self.assertIsNone(worker.run_once())
        self.assertEqual(self.processor.calls, 1)

    def test_dois_workers_nao_processam_mesmo_item(self):
        self.enqueue(); self.processor.block = True
        first = self.worker(); second = self.worker()
        thread = threading.Thread(target=first.run_once)
        thread.start(); self.assertTrue(self.processor.started.wait(2))
        self.assertIsNone(second.run_once())
        self.processor.release.set(); thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.processor.calls, 1)

    def test_dois_workers_nao_processam_mesmo_cancelamento(self):
        self.enqueue(operation="evento"); self.processor.block = True
        first = self.worker(); second = self.worker()
        thread = threading.Thread(target=first.run_once)
        thread.start(); self.assertTrue(self.processor.started.wait(2))
        self.assertIsNone(second.run_once())
        self.processor.release.set(); thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.processor.calls, 1)

    def test_heartbeat_renova_lease_e_impede_segundo_worker_apos_prazo_original(self):
        self.enqueue(); self.processor.block = True
        first = self.worker(lease_seconds=1, heartbeat_seconds=0.01)
        renewed = threading.Event()
        original_renew = first.outbox.renew_lease

        def observed_renew(*args, **kwargs):
            result = original_renew(*args, **kwargs)
            renewed.set()
            return result

        first.outbox.renew_lease = observed_renew
        thread = threading.Thread(target=first.run_once)
        thread.start(); self.assertTrue(self.processor.started.wait(2))
        original = self.outbox.list_items()[0]
        original_deadline = datetime.fromisoformat(original["lease_until"])
        self.assertTrue(renewed.wait(2))
        self.assertIsNone(self.outbox.claim_next(
            worker_id="segundo-worker", lease_seconds=1,
            now=original_deadline + timedelta(microseconds=1),
        ))
        active = self.outbox.list_items()[0]
        self.assertEqual(active["worker_id"], first.worker_id)
        self.processor.release.set(); thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_renovacao_de_lease_exige_worker_proprietario(self):
        item = self.enqueue()
        moment = datetime.fromisoformat(item["created_at"]) + timedelta(seconds=1)
        claimed = self.outbox.claim_item(
            int(item["id"]), worker_id="dono", lease_seconds=1, now=moment
        )
        self.assertIsNone(self.outbox.renew_lease(
            int(item["id"]), worker_id="intruso", lease_seconds=10,
            now=moment + timedelta(seconds=1),
        ))
        renewed = self.outbox.renew_lease(
            int(item["id"]), worker_id="dono", lease_seconds=10,
            now=moment + timedelta(seconds=1),
        )
        self.assertEqual(renewed["worker_id"], "dono")
        self.assertGreater(
            datetime.fromisoformat(renewed["lease_until"]),
            datetime.fromisoformat(claimed["lease_until"]),
        )

    def test_claim_perdido_impede_overwrite_tardio(self):
        item = self.enqueue()
        moment = datetime.fromisoformat(item["created_at"]) + timedelta(seconds=1)
        stale = self.outbox.claim_item(
            int(item["id"]), worker_id="antigo", lease_seconds=1, now=moment
        )
        current = self.outbox.claim_next(
            worker_id="novo", lease_seconds=30, now=moment + timedelta(seconds=2)
        )
        self.assertEqual(current["worker_id"], "novo")
        stale["status"] = "CONCLUIDO"
        with self.assertRaisesRegex(ValueError, "não pertence mais"):
            self.outbox.save_claimed_record(stale, worker_id="antigo", finish=True)
        latest = self.outbox.list_items()[0]
        self.assertEqual(latest["worker_id"], "novo")
        self.assertEqual(latest["status"], "PROCESSANDO")

    def test_resposta_desconhecida_e_somente_consultada(self):
        self.enqueue(status="RESPOSTA_DESCONHECIDA")
        result = self.worker().run_once()
        self.assertEqual(result["status"], "CONCLUIDO")
        self.assertEqual(self.processor.reconciliations, 1)
        self.assertEqual(self.processor.calls, 1)

    def test_recibo_pendente_e_consultado(self):
        self.enqueue(operation="recibo", receipt="123")
        self.worker().run_once()
        self.assertEqual(self.processor.calls, 1)

    def test_concluido_nao_retorna_ao_worker(self):
        self.enqueue(status="CONCLUIDO")
        self.assertIsNone(self.worker().run_once())

    def test_credencial_ausente_preserva_documento_sem_senha(self):
        self.enqueue(); self.processor.password = None
        result = self.worker().run_once()
        self.assertEqual(result["status"], "ERRO")
        self.assertEqual(result["last_status_code"], "AGUARDANDO_CREDENCIAL")
        self.assertNotIn("segredo", str(result))
        self.assertEqual(self.processor.calls, 0)

    def test_credencial_ausente_preserva_resposta_desconhecida(self):
        self.enqueue(status="RESPOSTA_DESCONHECIDA"); self.processor.password = None
        result = self.worker().run_once()
        self.assertEqual(result["status"], "RESPOSTA_DESCONHECIDA")
        self.assertEqual(result["last_status_code"], "AGUARDANDO_CREDENCIAL")

    def test_producao_continua_bloqueada(self):
        self.enqueue(environment="PRODUCAO")
        result = self.worker().run_once()
        self.assertEqual(result["status"], "FALHA")
        self.assertEqual(result["last_status_code"], "PRODUCAO_BLOQUEADA")
        self.assertEqual(self.processor.calls, 0)

    def test_falha_local_pre_envio_gera_backoff(self):
        self.enqueue()
        self.processor.process_transmission_queue = lambda **_: (_ for _ in ()).throw(
            ValueError("assinatura inválida")
        )
        before = datetime.now(timezone.utc)
        result = self.worker().run_once()
        self.assertEqual(result["status"], "ERRO")
        self.assertGreater(datetime.fromisoformat(result["next_attempt_at"]), before)

    def test_reinicio_recupera_pendencia(self):
        self.enqueue()
        first = self.worker(); second = self.worker()
        self.assertEqual(second.run_once()["status"], "CONCLUIDO")
        self.assertIsNone(first.run_once())

    def test_shutdown_em_idle(self):
        worker = self.worker(); worker.start()
        self.assertTrue(worker.stop(timeout=2))

    def test_shutdown_durante_processamento_aguarda_conclusao(self):
        self.enqueue(); self.processor.block = True
        worker = self.worker(); worker.start()
        self.assertTrue(self.processor.started.wait(2))
        stopped = []
        stopper = threading.Thread(target=lambda: stopped.append(worker.stop(timeout=3)))
        stopper.start(); time.sleep(0.05)
        self.assertTrue(worker.is_running)
        self.processor.release.set(); stopper.join(3)
        self.assertEqual(stopped, [True])
        self.assertFalse(worker.is_running)

    def test_shutdown_primeiro_timeout_nao_finge_encerramento(self):
        self.enqueue(); self.processor.block = True
        worker = self.worker(); worker.start()
        self.assertTrue(self.processor.started.wait(2))
        self.assertFalse(worker.stop(timeout=0.001))
        self.assertTrue(worker.is_running)
        self.processor.release.set()
        self.assertTrue(worker.stop(timeout=2))
        self.assertFalse(worker.is_running)

    def test_central_nao_fura_claim_ativo(self):
        item = self.enqueue()
        claimed = self.outbox.claim_item(int(item["id"]), worker_id="outro", lease_seconds=60)
        self.assertIsNotNone(claimed)
        service = FiscalService(
            self.processor.connection_factory, storage_dir=Path(self.temp.name) / "fiscal"
        )
        self.assertEqual(
            service.process_transmission_queue(password="x", queue_ids=[item["id"]]), []
        )

    def test_item_com_backoff_futuro_nao_e_reivindicado(self):
        item = self.enqueue()
        connection = self.processor.connection_factory()
        connection.execute(
            "UPDATE fiscal_outbox SET status='ERRO',next_attempt_at=? WHERE id=?",
            ((datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), int(item["id"])),
        )
        connection.commit(); connection.close()
        self.assertIsNone(self.worker().run_once())


if __name__ == "__main__":
    unittest.main()
