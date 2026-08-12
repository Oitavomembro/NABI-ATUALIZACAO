import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path

from database.maintenance import DatabaseMaintenanceService
from services.factory_reset_service import FactoryResetService


class FactoryResetServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "app.db"
        with closing(sqlite3.connect(self.db)) as conn:
            conn.executescript("""
                CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
                CREATE TABLE clientes(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT);
                CREATE TABLE produtos(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT);
                CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER REFERENCES clientes(id));
                CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER REFERENCES produtos(id));
                CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, description TEXT);
                INSERT INTO clientes(nome) VALUES ('CLIENTE REAL'), ('CLIENTE TESTE');
                INSERT INTO produtos(nome) VALUES ('PRODUTO REAL'), ('PRODUTO TESTE');
                INSERT INTO movimentacoes(cliente_id) VALUES (1), (2);
                INSERT INTO estoque_movimentacoes(produto_id) VALUES (2);
                INSERT INTO schema_migrations(version, description) VALUES (7, 'estrutura atual');
            """)
            conn.commit()
        maintenance = DatabaseMaintenanceService(self.db, Path(self.temp.name) / "backups", required_tables=("clientes", "produtos"))
        self.service = FactoryResetService(self.db, maintenance)

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_counts_rows(self):
        plan = self.service.plan("OPERATIONAL_DATA")
        self.assertEqual(plan.row_counts["clientes"], 2)
        self.assertEqual(plan.row_counts["produtos"], 2)

    def test_destructive_mode_requires_exact_confirmation(self):
        with self.assertRaises(ValueError):
            self.service.execute("OPERATIONAL_DATA", typed_confirmation="sim")

    def test_operational_reset_preserves_configuration(self):
        backup, _ = self.service.execute("OPERATIONAL_DATA", typed_confirmation="APAGAR TUDO")
        self.assertTrue(backup.is_file())
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM configuracoes").fetchone()[0], 0)

    def test_configuration_mode_uses_callback_and_backup(self):
        called = []
        backup, plan = self.service.execute("APPEARANCE", apply_configuration_reset=called.append)
        self.assertTrue(backup.is_file())
        self.assertEqual(called, ["APPEARANCE"])
        self.assertEqual(plan.total_rows, 0)

    def test_test_data_preview_counts_only_explicit_test_entities(self):
        plan = self.service.plan("TEST_DATA")
        self.assertEqual(plan.row_counts, {"produtos": 1, "clientes": 1})
        self.assertEqual(plan.total_rows, 2)

    def test_test_data_removes_only_test_entities_and_direct_dependencies(self):
        self.service.execute("TEST_DATA", typed_confirmation="APAGAR TUDO")
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT nome FROM clientes ORDER BY id").fetchall(), [("CLIENTE REAL",)])
            self.assertEqual(conn.execute("SELECT nome FROM produtos ORDER BY id").fetchall(), [("PRODUTO REAL",)])
            self.assertEqual(conn.execute("SELECT cliente_id FROM movimentacoes").fetchall(), [(1,)])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM estoque_movimentacoes").fetchone()[0], 0)

    def test_complete_reset_preserves_schema_migration_metadata(self):
        self.service.execute("COMPLETE", typed_confirmation="APAGAR TUDO", apply_configuration_reset=lambda _mode: None)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT version FROM schema_migrations").fetchall(), [(7,)])

    def test_configuration_callback_failure_restores_database_backup(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO configuracoes(chave, valor) VALUES ('tema', 'dark')")
            conn.commit()

        def failing_callback(_mode):
            with closing(sqlite3.connect(self.db)) as conn:
                conn.execute("UPDATE configuracoes SET valor='light' WHERE chave='tema'")
                conn.commit()
            raise RuntimeError("falha simulada")

        with self.assertRaises(RuntimeError):
            self.service.execute("APPEARANCE", apply_configuration_reset=failing_callback)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT valor FROM configuracoes WHERE chave='tema'").fetchone()[0], "dark")


if __name__ == "__main__":
    unittest.main()
