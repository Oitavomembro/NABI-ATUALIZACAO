import sqlite3
import tempfile
import unittest
from pathlib import Path

from repositories.system_repository import SystemRepository


class TrackingConnection:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def close(self):
        self.closed = True
        return self.connection.close()


class SystemRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        conn = sqlite3.connect(self.db)
        conn.executescript(
            """
            CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT);
            CREATE TABLE historico_clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                evento TEXT NOT NULL,
                detalhes TEXT,
                data TEXT NOT NULL
            );
            """
        )
        conn.close()
        self.connections = []

        def factory():
            tracked = TrackingConnection(sqlite3.connect(self.db))
            self.connections.append(tracked)
            return tracked

        self.repo = SystemRepository(factory)

    def tearDown(self):
        self.tmp.cleanup()

    def test_config_round_trip_and_default(self):
        self.assertEqual(self.repo.get_config("missing", "fallback"), "fallback")
        self.repo.set_config("theme", "dark")
        self.assertEqual(self.repo.get_config("theme"), "dark")
        self.assertTrue(all(item.closed for item in self.connections))

    def test_history_is_persisted(self):
        entry = self.repo.add_client_history(7, "EDIÇÃO", "Cadastro alterado", created_at="01/01/2026 10:00:00")
        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT cliente_id, evento, detalhes, data FROM historico_clientes").fetchone()
        conn.close()
        self.assertEqual(row, (7, "EDIÇÃO", "Cadastro alterado", "01/01/2026 10:00:00"))
        self.assertEqual(entry.client_id, 7)

    def test_write_failure_rolls_back_and_closes(self):
        bad_db = Path(self.tmp.name) / "bad.db"
        conn = sqlite3.connect(bad_db)
        conn.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT NOT NULL CHECK(valor <> 'invalid'))")
        conn.close()
        tracked = []

        def factory():
            item = TrackingConnection(sqlite3.connect(bad_db))
            tracked.append(item)
            return item

        repo = SystemRepository(factory)
        with self.assertRaises(sqlite3.IntegrityError):
            repo.set_config("x", "invalid")
        self.assertTrue(tracked[0].closed)
        check = sqlite3.connect(bad_db)
        self.assertEqual(check.execute("SELECT COUNT(*) FROM configuracoes").fetchone()[0], 0)
        check.close()

    def test_rejects_invalid_identifiers(self):
        with self.assertRaises(ValueError):
            self.repo.get_config("  ")
        with self.assertRaises(ValueError):
            self.repo.add_client_history(0, "TESTE")
        with self.assertRaises(ValueError):
            self.repo.add_client_history(1, "")


if __name__ == "__main__":
    unittest.main()
