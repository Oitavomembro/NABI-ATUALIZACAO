import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from services.cash_service import CashService


SCHEMA = """
CREATE TABLE cash_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,terminal TEXT NOT NULL,opened_by TEXT NOT NULL,opened_at TEXT NOT NULL,opening_balance TEXT NOT NULL,opening_mode TEXT NOT NULL,status TEXT NOT NULL,closed_by TEXT DEFAULT '',closed_at TEXT DEFAULT '',expected_cash TEXT,counted_cash TEXT,difference TEXT,closing_note TEXT DEFAULT '');
CREATE UNIQUE INDEX one_open_cash ON cash_sessions(terminal) WHERE status='ABERTO';
CREATE TABLE cash_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,cash_session_id INTEGER NOT NULL,type TEXT NOT NULL,amount TEXT NOT NULL,payment_method TEXT DEFAULT 'DINHEIRO',source TEXT DEFAULT 'CAIXA',source_id TEXT DEFAULT '',user_id TEXT NOT NULL,note TEXT DEFAULT '',created_at TEXT NOT NULL);
CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,tipo TEXT,forma_pagamento TEXT,valor REAL,valor_decimal TEXT,data TEXT,status_pagamento TEXT DEFAULT 'PAGO');
CREATE TABLE auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,usuario TEXT,modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
"""


class CashSessionCheckpoint41Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "cash41.db"
        conn = sqlite3.connect(self.db); conn.executescript(SCHEMA); conn.close()
        self.cash = CashService(lambda: sqlite3.connect(self.db))
        self.opened = "12/08/2026 08:00:00"

    def tearDown(self): self.tmp.cleanup()

    def open(self, user="Joao", value="100.00", mode="VALOR_INFORMADO"):
        return self.cash.open_session("PC-CAIXA", user, value, mode, self.opened)

    def movement(self, kind, method, value, at="12/08/2026 09:00:00"):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO movimentacoes(tipo,forma_pagamento,valor,valor_decimal,data) VALUES(?,?,?,?,?)", (kind, method, float(value), str(value), at)); conn.commit(); conn.close()

    def test_opening_with_informed_balance_and_audit(self):
        session = self.open(value="25.50")
        self.assertEqual(session.opening_balance, Decimal("25.50")); self.assertEqual(session.opened_by, "Joao")
        conn = sqlite3.connect(self.db); self.assertEqual(conn.execute("SELECT acao FROM auditoria").fetchone()[0], "CAIXA_ABERTO"); conn.close()

    def test_opening_without_value_is_zero_and_has_no_cancel_mode(self):
        session = self.open(value="999", mode="SEM_VALOR_INFORMADO")
        self.assertEqual(session.opening_balance, Decimal("0.00"))
        self.assertEqual(session.opening_mode, "SEM_VALOR_INFORMADO")
        with self.assertRaises(ValueError): self.cash.open_session("OUTRO", "Ana", 0, "CANCELAR")

    def test_prevents_two_open_sessions_on_same_terminal(self):
        self.open()
        with self.assertRaises(FileExistsError): self.open(user="Maria")

    def test_user_switch_keeps_terminal_session(self):
        first = self.open(user="Joao")
        self.cash.register_session_movement("PC-CAIXA", "SUPRIMENTO", 10, "Maria", "troco", "12/08/2026 09:00:00")
        self.assertEqual(self.cash.get_open_session("PC-CAIXA").id, first.id)
        self.assertEqual(self.cash.session_summary(first.id)["movements"][0]["usuario"], "Maria")

    def test_sales_payment_methods_split_movement_from_drawer(self):
        session = self.open(value=0)
        self.movement("COMPRA", "DINHEIRO R$ 50.00 + PIX R$ 20.00 + CARTÃO R$ 30.00", 100)
        summary = self.cash.session_summary(session.id)
        self.assertEqual(summary["dinheiro"], 50); self.assertEqual(summary["pix"], 20); self.assertEqual(summary["cartao"], 30)
        self.assertEqual(summary["movement_total"], 100); self.assertEqual(summary["expected_cash"], 50)

    def test_cash_and_pix_receipts_are_classified(self):
        session = self.open(value=0)
        self.movement("PAGAMENTO", "Dinheiro", 40); self.movement("PAGAMENTO", "PIX", 25)
        summary = self.cash.session_summary(session.id)
        self.assertEqual(summary["recebimentos_dinheiro"], 40); self.assertEqual(summary["recebimentos_eletronicos"], 25)
        self.assertEqual(summary["expected_cash"], 40)

    def test_cancelled_sale_does_not_affect_cash(self):
        session = self.open(value=10)
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO movimentacoes(tipo,forma_pagamento,valor,valor_decimal,data,status_pagamento) VALUES('COMPRA','Dinheiro',50,'50.00','12/08/2026 09:00:00','CANCELADO')")
        conn.commit(); conn.close()
        self.assertEqual(self.cash.session_summary(session.id)["expected_cash"], 10)

    def test_sangria_and_suprimento_update_expected_and_audit(self):
        session = self.open()
        self.cash.register_session_movement("PC-CAIXA", "SANGRIA", 30, "Ana", "cofre", "12/08/2026 09:00:00")
        self.cash.register_session_movement("PC-CAIXA", "SUPRIMENTO", 20, "Bia", "troco", "12/08/2026 10:00:00")
        summary = self.cash.session_summary(session.id)
        self.assertEqual(summary["expected_cash"], 90)
        conn = sqlite3.connect(self.db); self.assertEqual(conn.execute("SELECT COUNT(*) FROM auditoria WHERE acao IN ('SANGRIA','SUPRIMENTO')").fetchone()[0], 2); conn.close()

    def test_invalid_movement_and_closed_session_are_rejected(self):
        self.open(value=0)
        with self.assertRaises(ValueError): self.cash.register_session_movement("PC-CAIXA", "SANGRIA", 0, "Ana")
        self.cash.close_session("PC-CAIXA", 0, "Ana", closed_at="12/08/2026 18:00:00")
        with self.assertRaises(RuntimeError): self.cash.register_session_movement("PC-CAIXA", "SUPRIMENTO", 10, "Ana")

    def test_closing_equal_surplus_shortage_and_note_rule(self):
        self.open(value=100)
        equal = self.cash.close_session("PC-CAIXA", 100, "Ana", closed_at="12/08/2026 18:00:00")
        self.assertEqual(equal.difference, 0); self.assertEqual(equal.closed_by, "Ana")
        self.cash.open_session("PC-CAIXA", "Bia", 100, opened_at="13/08/2026 08:00:00")
        with self.assertRaises(ValueError): self.cash.close_session("PC-CAIXA", 110, "Bia", closed_at="13/08/2026 18:00:00")
        surplus = self.cash.close_session("PC-CAIXA", 110, "Bia", "sobra apurada", "13/08/2026 18:00:00")
        self.assertEqual(surplus.difference, 10)
        self.cash.open_session("PC-CAIXA", "Caio", 100, opened_at="14/08/2026 08:00:00")
        shortage = self.cash.close_session("PC-CAIXA", 90, "Caio", "falta apurada", "14/08/2026 18:00:00")
        self.assertEqual(shortage.difference, -10)

    def test_history_is_snapshot_and_new_opening_only_after_close(self):
        session = self.open(value=100); self.movement("COMPRA", "Dinheiro", 20)
        closed = self.cash.close_session("PC-CAIXA", 120, "Ana", closed_at="12/08/2026 18:00:00")
        self.movement("COMPRA", "Dinheiro", 999, at="12/08/2026 19:00:00")
        history = self.cash.history("PC-CAIXA")
        self.assertEqual(history[0].expected_cash, Decimal("120.00")); self.assertEqual(closed.id, session.id)
        new = self.cash.open_session("PC-CAIXA", "Maria", 0, "SEM_VALOR_INFORMADO", "13/08/2026 08:00:00")
        self.assertNotEqual(new.id, session.id)


if __name__ == "__main__": unittest.main()
