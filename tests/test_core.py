from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core import ConfigManager, EventBus


class ConfigManagerTests(unittest.TestCase):
    def test_defaults_nested_get_and_atomic_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config" / "sistema.json"
            manager = ConfigManager(path, {"app": {"version": "2.4.4"}, "backup": {"enabled": True}})
            self.assertEqual(manager.get("app.version"), "2.4.4")
            manager.set("backup.keep", 10)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["backup"]["keep"], 10)

    def test_corrupt_json_is_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sistema.json"
            path.write_text("{arquivo inválido", encoding="utf-8")
            manager = ConfigManager(path, {"safe": True})
            self.assertTrue(manager.get("safe"))
            self.assertTrue(path.exists())


class EventBusTests(unittest.TestCase):
    def test_publish_and_unsubscribe(self):
        bus = EventBus()
        received = []
        subscription = bus.subscribe("produto.salvo", lambda produto_id: received.append(produto_id))
        bus.publish("produto.salvo", produto_id=42)
        self.assertEqual(received, [42])
        self.assertTrue(bus.unsubscribe(subscription))
        bus.publish("produto.salvo", produto_id=43)
        self.assertEqual(received, [42])

    def test_handler_failure_does_not_stop_other_handlers(self):
        bus = EventBus()
        received = []
        bus.subscribe("teste", lambda **_: (_ for _ in ()).throw(RuntimeError("erro esperado")))
        bus.subscribe("teste", lambda value: received.append(value))
        bus.publish("teste", value="ok")
        self.assertEqual(received, ["ok"])


if __name__ == "__main__":
    unittest.main()
