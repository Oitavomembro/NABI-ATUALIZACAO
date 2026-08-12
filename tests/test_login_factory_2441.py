import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from database.maintenance import DatabaseMaintenanceService
from services.factory_reset_service import FactoryResetService


class LoginAndFactory2441Tests(unittest.TestCase):
    def test_startup_migration_forces_login_off_once(self):
        source = Path("nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn('login_politica_v2442_inicializada', source)
        marker = source.index('login_politica_v2442_inicializada')
        block = source[marker:marker + 650]
        self.assertIn('salvar_config("login_usuarios_habilitado", "0")', block)
        self.assertIn('salvar_config("login_inicio_ativado_pelo_usuario_v2442", "0")', block)

    def test_startup_does_not_open_login_automatically(self):
        source = Path("nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertNotIn("self.after(50, self.abrir_login_usuario)", source)

    def test_dependency_order_places_child_tables_before_parents(self):
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.executescript("""
                CREATE TABLE clientes(id INTEGER PRIMARY KEY);
                CREATE TABLE vendas(id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id));
                CREATE TABLE venda_itens(id INTEGER PRIMARY KEY, venda_id INTEGER REFERENCES vendas(id));
            """)
            order = FactoryResetService._dependency_order(conn, ("clientes", "vendas", "venda_itens"))
        self.assertEqual(order[:2], ("venda_itens", "vendas"))

    def test_complete_reset_handles_legacy_foreign_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "legacy.db"
            with closing(sqlite3.connect(db)) as conn:
                conn.executescript("""
                    PRAGMA foreign_keys=ON;
                    CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY);
                    CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
                    CREATE TABLE clientes(id INTEGER PRIMARY KEY);
                    CREATE TABLE vendas(id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id));
                    CREATE TABLE venda_itens(id INTEGER PRIMARY KEY, venda_id INTEGER REFERENCES vendas(id));
                    INSERT INTO schema_migrations VALUES (13);
                    INSERT INTO configuracoes VALUES ('nome_loja', 'Teste');
                    INSERT INTO clientes VALUES (1);
                    INSERT INTO vendas VALUES (1, 1);
                    INSERT INTO venda_itens VALUES (1, 1);
                """)
                conn.commit()
            maintenance = DatabaseMaintenanceService(db, Path(tmp) / "backups", required_tables=("clientes",))
            service = FactoryResetService(db, maintenance)
            service.execute("COMPLETE", typed_confirmation="APAGAR TUDO", apply_configuration_reset=lambda _mode: None)
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM vendas").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM venda_itens").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT version FROM schema_migrations").fetchone()[0], 13)
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
