from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
SERVICE_SOURCE = (ROOT / "services" / "mysql_migration_service.py").read_text(encoding="utf-8")


class MigrationPhase2ForeignKeyTests(unittest.TestCase):
    def test_legacy_entrypoint_delegates_without_duplicating_rules(self):
        start = LEGACY_SOURCE.index("def executar_migracao_resumida")
        end = LEGACY_SOURCE.index("def _data_sql", start)
        entrypoint = LEGACY_SOURCE[start:end]
        self.assertIn("_MYSQL_MIGRATION_SERVICE.execute_summary", entrypoint)
        self.assertNotIn("BEGIN IMMEDIATE", entrypoint)
        self.assertNotIn("INSERT INTO movimentacoes", entrypoint)

    def test_legacy_entrypoint_preserves_runtime_dependencies(self):
        start = LEGACY_SOURCE.index("def executar_migracao_resumida")
        end = LEGACY_SOURCE.index("def _data_sql", start)
        entrypoint = LEGACY_SOURCE[start:end]
        for dependency in (
            "database_path=DB_NAME",
            "backup_dir=BACKUP_DIR",
            "connect=conectar_banco",
            "backup_database=backup_database",
            "network_mode=MODO_REDE",
            "remove_demo_clients=remover_demos",
            "progress=progresso",
        ):
            self.assertIn(dependency, entrypoint)

    def test_reimport_updates_movements_in_place(self):
        self.assertIn("SELECT id FROM movimentacoes WHERE origem_sistema=? AND origem_id=?", SERVICE_SOURCE)
        self.assertIn("UPDATE movimentacoes SET cliente_id=?", SERVICE_SOURCE)
        self.assertNotIn(
            "DELETE FROM movimentacoes WHERE cliente_id=? AND origem_sistema='FICHARIO_MYSQL'",
            SERVICE_SOURCE,
        )

    def test_migration_validates_foreign_keys_before_commit(self):
        self.assertIn("PRAGMA foreign_key_check", SERVICE_SOURCE)
        self.assertIn("Integridade inválida após migração", SERVICE_SOURCE)

    def test_demo_cleanup_uses_child_to_parent_order_and_savepoint(self):
        start = SERVICE_SOURCE.index("def remove_demo_client")
        end = SERVICE_SOURCE.index("try:\n            cursor.execute(\"BEGIN IMMEDIATE\")", start)
        section = SERVICE_SOURCE[start:end]
        self.assertLess(section.index("DELETE FROM documentos_emitidos"), section.index("DELETE FROM movimentacoes"))
        self.assertLess(section.index("DELETE FROM parcelas"), section.index("DELETE FROM movimentacoes"))
        self.assertLess(section.index("DELETE FROM movimentacoes"), section.index("DELETE FROM clientes"))
        self.assertIn("SAVEPOINT remover_demo", section)
        self.assertIn("ROLLBACK TO SAVEPOINT remover_demo", section)


if __name__ == "__main__":
    unittest.main()
