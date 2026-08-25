import sqlite3
import tempfile
import unittest
import inspect
from pathlib import Path

from services.admin_audit_service import AdminAuditService


class TrackingConnection:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def close(self):
        self.closed = True
        return self.connection.close()


class AdminAuditServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "audit.db"
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE log_acesso_admin(id INTEGER PRIMARY KEY, data TEXT, sucesso INTEGER, detalhes TEXT);
            CREATE TABLE auditoria(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT, usuario TEXT, modulo TEXT, acao TEXT, objeto TEXT, detalhes TEXT, resultado TEXT
            );
            INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado)
            VALUES('01/01/2026','ana','SEGURANCA','LOGIN','usuario:ana','Acesso autorizado','SUCESSO');
            INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado)
            VALUES('02/01/2026','bob','FINANCEIRO','BAIXA','titulo:1','Pagamento','SUCESSO');
            """
        )
        connection.close()
        self.connections = []

        def factory():
            tracked = TrackingConnection(sqlite3.connect(self.db))
            self.connections.append(tracked)
            return tracked

        self.service = AdminAuditService(factory)

    def tearDown(self):
        self.tmp.cleanup()

    def test_records_admin_access_and_closes_connection(self):
        self.service.record_admin_access(True, "Senha correta", occurred_at="03/01/2026")
        connection = sqlite3.connect(self.db)
        row = connection.execute("SELECT data,sucesso,detalhes FROM log_acesso_admin").fetchone()
        connection.close()
        self.assertEqual(row, ("03/01/2026", 1, "Senha correta"))
        self.assertTrue(all(item.closed for item in self.connections))

    def test_lists_only_security_audit(self):
        rows = self.service.list_security_audit()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].user, "ana")
        self.assertEqual(rows[0].action, "LOGIN")

    def test_rejects_empty_details_without_opening_connection(self):
        with self.assertRaises(ValueError):
            self.service.record_admin_access(False, "  ")
        self.assertEqual(self.connections, [])

    def test_write_failure_rolls_back_and_closes(self):
        bad = Path(self.tmp.name) / "bad.db"
        connection = sqlite3.connect(bad)
        connection.execute("CREATE TABLE log_acesso_admin(id INTEGER PRIMARY KEY, data TEXT, sucesso INTEGER, detalhes TEXT CHECK(detalhes <> 'falha'))")
        connection.close()
        tracked = []

        def factory():
            item = TrackingConnection(sqlite3.connect(bad))
            tracked.append(item)
            return item

        service = AdminAuditService(factory)
        with self.assertRaises(sqlite3.IntegrityError):
            service.record_admin_access(False, "falha")
        self.assertTrue(tracked[0].closed)
        check = sqlite3.connect(bad)
        self.assertEqual(check.execute("SELECT COUNT(*) FROM log_acesso_admin").fetchone()[0], 0)
        check.close()

    def test_evento_critico_nunca_cai_em_best_effort(self):
        connection = sqlite3.connect(self.db)
        connection.execute(
            "CREATE TRIGGER bloquear_auditoria BEFORE INSERT ON auditoria "
            "BEGIN SELECT RAISE(ABORT, 'auditoria indisponivel'); END"
        )
        connection.close()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "auditoria indisponivel"):
            self.service.record_event("CAIXA", "SANGRIA", object_id="1")

    def test_evento_informativo_continua_best_effort(self):
        connection = sqlite3.connect(self.db)
        connection.execute(
            "CREATE TRIGGER bloquear_auditoria BEFORE INSERT ON auditoria "
            "BEGIN SELECT RAISE(ABORT, 'auditoria indisponivel'); END"
        )
        connection.close()
        self.service.record_event("IA_NABI", "CONSULTA_FERRAMENTA", object_id="busca")

    def test_catalogo_cobre_familias_criticas_documentadas(self):
        from services.critical_audit_policy import is_critical_event

        eventos = (
            ("SEGURANCA", "ALTERAR_SENHA"), ("CAIXA", "CAIXA_FECHADO"),
            ("FINANCEIRO", "ESTORNAR_PAGAMENTO"), ("ESTOQUE", "AJUSTE"),
            ("COMPRAS", "RECEBER"), ("SISTEMA", "RESTAURAR"),
            ("LICENCIAMENTO", "REVOGAR"), ("FISCAL", "CANCELAR"),
        )
        self.assertTrue(all(is_critical_event(*evento) for evento in eventos))

    def test_confirmacao_nabi_nao_possui_fallback_best_effort(self):
        from assistant_nabi.adapters import AdminAssistantConfirmationAuditAdapter

        source = inspect.getsource(AdminAssistantConfirmationAuditAdapter.record)
        self.assertIn("record_event_strict", source)
        self.assertNotIn("recorder = self._audit.record_event", source)


if __name__ == "__main__":
    unittest.main()
