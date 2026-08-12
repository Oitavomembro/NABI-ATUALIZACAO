import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import DatabaseMaintenanceService, Migration


class DatabaseMaintenanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "app.db"
        connection = sqlite3.connect(self.database)
        connection.executescript("""
            CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT);
            INSERT INTO configuracoes(chave, valor) VALUES('db_schema_version', '1');
            CREATE TABLE produtos (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
            INSERT INTO produtos(nome) VALUES('ORIGINAL');
        """)
        connection.commit()
        connection.close()
        self.service = DatabaseMaintenanceService(
            self.database,
            self.root / "backups",
            expected_schema_version=1,
            required_tables=("configuracoes", "produtos"),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_backup_is_created_and_validated(self):
        path, report = self.service.create_backup(prefix="manual")
        self.assertTrue(path.is_file())
        self.assertTrue(report.valid)

    def test_backup_closes_source_when_destination_open_fails(self):
        class SourceConnection:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        source = SourceConnection()
        with patch.object(
            self.service,
            "_connect",
            side_effect=[source, sqlite3.OperationalError("destino indisponÃ­vel")],
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self.service.create_backup()
        self.assertTrue(source.closed)

    def test_restore_creates_safety_backup_and_restores_data(self):
        backup, _ = self.service.create_backup()
        connection = sqlite3.connect(self.database)
        connection.execute("UPDATE produtos SET nome='ALTERADO'")
        connection.commit()
        connection.close()
        safety, report = self.service.restore(backup)
        self.assertTrue(safety.is_file())
        self.assertTrue(report.valid)
        connection = sqlite3.connect(self.database)
        name = connection.execute("SELECT nome FROM produtos").fetchone()[0]
        connection.close()
        self.assertEqual(name, "ORIGINAL")

    def test_invalid_backup_is_rejected_without_changing_database(self):
        invalid = self.root / "invalid.db"
        invalid.write_bytes(b"not sqlite")
        with self.assertRaises(sqlite3.DatabaseError):
            self.service.restore(invalid)
        connection = sqlite3.connect(self.database)
        self.assertEqual(connection.execute("SELECT nome FROM produtos").fetchone()[0], "ORIGINAL")
        connection.close()

    def test_failed_migration_rolls_back(self):
        def broken(connection):
            connection.execute("CREATE TABLE parcial(id INTEGER)")
            raise RuntimeError("falha")

        with self.assertRaises(RuntimeError):
            self.service.run_migrations([Migration(2, broken)])
        connection = sqlite3.connect(self.database)
        table = connection.execute("SELECT 1 FROM sqlite_master WHERE name='parcial'").fetchone()
        version = connection.execute("SELECT valor FROM configuracoes WHERE chave='db_schema_version'").fetchone()[0]
        connection.close()
        self.assertIsNone(table)
        self.assertEqual(version, "1")

    def test_report_is_exported(self):
        output = self.service.export_report(self.root / "reports" / "database.json")
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(data["valid"])
        self.assertEqual(data["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
