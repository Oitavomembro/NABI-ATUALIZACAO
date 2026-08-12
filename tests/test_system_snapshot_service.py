import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from services.system_snapshot_service import SystemSnapshotService


class SystemSnapshotServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db_path = root / "app.db"
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("CREATE TABLE dados (id INTEGER PRIMARY KEY, valor TEXT)")
            connection.execute("INSERT INTO dados(valor) VALUES ('original')")
            connection.commit()
        finally:
            connection.close()
        self.service = SystemSnapshotService(
            DatabaseManager(self.db_path),
            rollback_dir=root / "rollback",
            update_state_file=root / "estado.json",
            app_version="2.4.32",
            schema_version=32,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_create_list_and_restore(self):
        snapshot = self.service.create("teste seguro")
        listed = self.service.list()
        self.assertEqual(snapshot["id"], listed[0]["id"])
        self.assertTrue(listed[0]["valido"])

        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("UPDATE dados SET valor='alterado'")
            connection.commit()
        finally:
            connection.close()

        safety = self.service.restore(snapshot["id"])
        self.assertIn("antes_do_rollback", safety["motivo"])
        connection = sqlite3.connect(self.db_path)
        try:
            value = connection.execute("SELECT valor FROM dados").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual("original", value)

    def test_tampered_snapshot_is_invalid(self):
        snapshot = self.service.create("tamper")
        database_path = Path(snapshot["banco_snapshot"])
        database_path.write_bytes(database_path.read_bytes() + b"adulterado")
        listed = self.service.list()
        self.assertFalse(listed[0]["valido"])
        with self.assertRaises(ValueError):
            self.service.restore(snapshot["id"])

    def test_manifest_and_state_are_valid_json(self):
        snapshot = self.service.create("json")
        manifest_path = Path(snapshot["banco_snapshot"]).parent / "manifesto.json"
        self.assertEqual(snapshot["id"], json.loads(manifest_path.read_text(encoding="utf-8"))["id"])
