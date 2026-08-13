import threading
import time
import unittest

from core import EventBus, TaskManager, TaskStatus


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.manager = TaskManager(max_workers=2, event_bus=self.bus)

    def tearDown(self):
        self.manager.shutdown(wait=True, cancel_pending=True)

    def test_conclui_tarefa_e_publica_eventos(self):
        events = []
        self.bus.subscribe("tarefa.concluida", lambda **payload: events.append(payload))

        record = self.manager.submit("soma", lambda ctx: 20 + 22)
        final = self.manager.wait(record.id, timeout=2)

        self.assertEqual(final.status, TaskStatus.COMPLETED)
        self.assertEqual(final.result, 42)
        self.assertEqual(final.progress, 1.0)
        self.assertEqual(events[0]["task_id"], record.id)

    def test_progresso_e_mensagem(self):
        def work(ctx):
            ctx.report_progress(0.25, "iniciando")
            ctx.report_progress(0.75, "finalizando")
            return "ok"

        final = self.manager.wait(self.manager.submit("progresso", work).id, timeout=2)
        self.assertEqual(final.status, TaskStatus.COMPLETED)
        self.assertEqual(final.message, "finalizando")

    def test_cancelamento_cooperativo(self):
        started = threading.Event()

        def work(ctx):
            started.set()
            while True:
                ctx.check_cancelled()
                time.sleep(0.01)

        record = self.manager.submit("cancelar", work)
        self.assertTrue(started.wait(1))
        self.assertTrue(self.manager.cancel(record.id))
        final = self.manager.wait(record.id, timeout=2)
        self.assertEqual(final.status, TaskStatus.CANCELLED)

    def test_falha_fica_registrada(self):
        def fail(_ctx):
            raise RuntimeError("erro controlado")

        final = self.manager.wait(self.manager.submit("falha", fail).id, timeout=2)
        self.assertEqual(final.status, TaskStatus.FAILED)
        self.assertIn("erro controlado", final.error)

    def test_historico_remove_concluidas_antigas_sem_afetar_recentes(self):
        manager = TaskManager(max_workers=1, max_records=3)
        try:
            completed = []
            for index in range(4):
                record = manager.submit(f"tarefa {index}", lambda _ctx, value=index: value)
                completed.append(manager.wait(record.id, timeout=2))
            records = manager.list()
            self.assertEqual(len(records), 3)
            self.assertIsNone(manager.get(completed[0].id))
            self.assertEqual({item.result for item in records}, {1, 2, 3})
        finally:
            manager.shutdown(wait=True, cancel_pending=True)

    def test_limite_invalido_e_rejeitado(self):
        with self.assertRaises(ValueError):
            TaskManager(max_records=0)


if __name__ == "__main__":
    unittest.main()
