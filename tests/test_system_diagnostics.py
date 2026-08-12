from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from services.system_diagnostics import SystemDiagnostics


class SystemDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db_path = self.root / "nabicode.db"
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT);
            INSERT INTO configuracoes(chave, valor) VALUES('db_schema_version', '4');
            CREATE TABLE clientes(id INTEGER PRIMARY KEY);
            CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY);
            CREATE TABLE categorias(id INTEGER PRIMARY KEY);
            CREATE TABLE produtos(id INTEGER PRIMARY KEY);
            """
        )
        connection.close()
        self.diagnostics = SystemDiagnostics(
            DatabaseManager(self.db_path),
            app_dir=self.root,
            backup_dir=self.root / "backups",
            rollback_dir=self.root / "rollback",
            diagnostic_dir=self.root / "diagnosticos",
            app_version="2.4.6",
            schema_version=4,
            required_tables={"clientes", "movimentacoes", "configuracoes", "categorias", "produtos"},
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_healthy_database_is_approved_and_report_is_saved(self):
        snapshot = self.root / "rollback" / "snapshot"
        snapshot.mkdir(parents=True)
        (snapshot / "banco.db").write_bytes(self.db_path.read_bytes())
        report = self.diagnostics.run()
        self.assertTrue(report["aprovado"])
        self.assertTrue(Path(report["arquivo"]).is_file())
        saved = json.loads(Path(report["arquivo"]).read_text(encoding="utf-8"))
        self.assertEqual(saved["versao_app"], "2.4.6")

    def test_missing_required_table_fails(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute("DROP TABLE produtos")
        connection.commit()
        connection.close()
        report = self.diagnostics.run(save_report=False)
        check = next(item for item in report["checks"] if item["name"] == "Tabelas obrigatórias")
        self.assertFalse(check["ok"])
        self.assertFalse(report["aprovado"])

    def test_schema_mismatch_fails(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute("UPDATE configuracoes SET valor='3' WHERE chave='db_schema_version'")
        connection.commit()
        connection.close()
        report = self.diagnostics.run(save_report=False)
        check = next(item for item in report["checks"] if item["name"] == "Versão do esquema")
        self.assertFalse(check["ok"])

    def test_formatter_contains_result(self):
        report = self.diagnostics.run(save_report=False)
        text = self.diagnostics.format_report(report)
        self.assertIn("DIAGNÓSTICO NABICODE", text)
        self.assertIn("RESULTADO:", text)


if __name__ == "__main__":
    unittest.main()
