from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.schema_initializer import initialize_database


class SchemaInitializerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "nabicode.db"
        self.backup_dir = self.root / "backups"
        self.pdf_dir = self.root / "pdfs"
        self.backups: list[tuple[int, int]] = []

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def read_version(self) -> int:
        if not self.db_path.exists():
            return 0
        connection = sqlite3.connect(self.db_path)
        try:
            row = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
            ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error:
            return 0
        finally:
            connection.close()

    def backup(self, source: int, target: int) -> str:
        self.backups.append((source, target))
        return str(self.backup_dir / f"v{source}_v{target}.db")

    def initialize(self, version: int = 32) -> None:
        initialize_database(
            db_name=str(self.db_path),
            backup_dir=str(self.backup_dir),
            pdf_dir=str(self.pdf_dir),
            schema_version=version,
            last_database_update={"executada": False, "de": 0, "para": version, "backup": ""},
            network_mode=False,
            network_role="local",
            connect=self.connect,
            read_existing_version=self.read_version,
            backup_before_update=self.backup,
        )

    def test_first_install_creates_core_schema_and_version(self):
        self.initialize()
        connection = sqlite3.connect(self.db_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("clientes", tables)
            self.assertIn("produtos", tables)
            self.assertIn("movimentacoes", tables)
            self.assertIn("configuracoes", tables)
            self.assertIn("fiscal_outbox", tables)
            self.assertIn("cash_closing_journal", tables)
            product_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(produtos)")
            }
            self.assertTrue({
                "fiscal_origin", "fiscal_csosn", "fiscal_icms_cst", "fiscal_icms_rate",
                "fiscal_pis_cst", "fiscal_pis_rate", "fiscal_cofins_cst",
                "fiscal_cofins_rate", "fiscal_profile_source",
            }.issubset(product_columns))
            movement_indexes = {
                row[1] for row in connection.execute("PRAGMA index_list(movimentacoes)")
            }
            self.assertIn("idx_mov_tipo_data", movement_indexes)
            cash_indexes = {
                row[1] for row in connection.execute("PRAGMA index_list(cash_sessions)")
            }
            self.assertIn("idx_cash_sessions_terminal_opened", cash_indexes)
            nfe_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(nfe_importacoes)")
            }
            self.assertIn("valor_total", nfe_columns)
            version = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
            ).fetchone()[0]
            self.assertEqual("32", version)
            self.assertEqual(
                "COMERCIAL",
                connection.execute(
                    "SELECT valor FROM configuracoes WHERE chave='modo_operacao'"
                ).fetchone()[0],
            )
        finally:
            connection.close()
        self.assertEqual([], self.backups)

    def test_repeated_initialization_is_idempotent(self):
        self.initialize()
        self.initialize()
        connection = sqlite3.connect(self.db_path)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM clientes WHERE codigo IN ('CLI001','CLI002')"
            ).fetchone()[0]
            self.assertEqual(2, count)
        finally:
            connection.close()

    def test_schema_21_backfill_legacy_tax_rule_is_append_only_and_idempotent(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript("""
                CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT);
                INSERT INTO configuracoes VALUES ('db_schema_version', '20');
                CREATE TABLE fiscal_tax_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,active INTEGER NOT NULL,
                    issuer_state TEXT NOT NULL,destination_state TEXT NOT NULL,tax_regime TEXT NOT NULL,
                    ncm_prefix TEXT NOT NULL,cest TEXT NOT NULL,operation_kind TEXT NOT NULL,
                    icms_code TEXT NOT NULL,icms_rate TEXT NOT NULL,icms_base_reduction TEXT NOT NULL,
                    sn_credit_rate TEXT NOT NULL,st_mva TEXT NOT NULL,st_rate TEXT NOT NULL,
                    fcp_st_rate TEXT NOT NULL,difal_internal_rate TEXT NOT NULL,
                    difal_interstate_rate TEXT NOT NULL,difal_fcp_rate TEXT NOT NULL,
                    benefit_code TEXT NOT NULL,approved_by TEXT NOT NULL,approved_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,updated_at TEXT NOT NULL
                );
                INSERT INTO fiscal_tax_rules VALUES
                    (1,'Legada',1,'BA','*','SIMPLES_NACIONAL','9403','','VENDA','102',
                     '0','0','0','0','0','0','0','0','0','','CONTADOR','2026-08-20',
                     '2026-08-20T10:00:00-03:00','2026-08-20T10:00:00-03:00');
            """)
            connection.commit()
        finally:
            connection.close()

        self.initialize(version=21)
        self.initialize(version=21)
        connection = sqlite3.connect(self.db_path)
        try:
            rows = connection.execute(
                "SELECT event_kind,actor,revision_number FROM fiscal_tax_rule_revisions WHERE rule_id=1"
            ).fetchall()
            self.assertEqual([("LEGACY_SEM_TRILHA", "NAO_INFORMADO", 1)], rows)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM fiscal_tax_rule_revisions WHERE rule_id=1")
        finally:
            connection.close()
        self.assertEqual([(20, 21)], self.backups)

    def test_legacy_products_table_without_nome_is_migrated_before_indexes(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("CREATE TABLE produtos(id INTEGER PRIMARY KEY, codigo TEXT, descricao TEXT)")
            connection.execute("INSERT INTO produtos(codigo, descricao) VALUES('P1', 'Produto legado')")
            connection.commit()
        finally:
            connection.close()

        self.initialize()

        connection = sqlite3.connect(self.db_path)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(produtos)")}
            self.assertIn("nome", columns)
            self.assertEqual(
                "Produto legado",
                connection.execute("SELECT nome FROM produtos WHERE codigo='P1'").fetchone()[0],
            )
            indexes = {row[1] for row in connection.execute("PRAGMA index_list(produtos)")}
            self.assertIn("idx_produtos_nome", indexes)
        finally:
            connection.close()

    def test_upgrade_requests_backup_and_records_migration(self):
        self.initialize(version=31)
        self.initialize(version=32)
        self.assertEqual([(31, 32)], self.backups)
        connection = sqlite3.connect(self.db_path)
        try:
            version = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
            ).fetchone()[0]
            self.assertEqual("32", version)
            migration = connection.execute(
                "SELECT versao_destino FROM schema_migrations WHERE versao_destino=32"
            ).fetchone()
            self.assertIsNotNone(migration)
        finally:
            connection.close()

    def test_interrupted_migration_does_not_persist_partial_schema(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript("""
                CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT);
                INSERT INTO configuracoes VALUES ('db_schema_version', '1');
                CREATE TRIGGER reject_target_version
                BEFORE INSERT ON configuracoes
                WHEN NEW.chave='db_schema_version' AND NEW.valor='32'
                BEGIN
                    SELECT RAISE(ABORT, 'falha simulada');
                END;
            """)
            connection.commit()
        finally:
            connection.close()

        opened = []

        def tracked_connect():
            current = self.connect()
            opened.append(current)
            return current

        with self.assertRaises(sqlite3.IntegrityError):
            initialize_database(
                db_name=str(self.db_path),
                backup_dir=str(self.backup_dir),
                pdf_dir=str(self.pdf_dir),
                schema_version=32,
                last_database_update={"executada": False, "de": 0, "para": 32, "backup": ""},
                network_mode=False,
                network_role="local",
                connect=tracked_connect,
                read_existing_version=self.read_version,
                backup_before_update=self.backup,
            )
        for current in opened:
            current.close()

        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                "1",
                connection.execute(
                    "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
                ).fetchone()[0],
            )
            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='clientes'"
                ).fetchone()
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
