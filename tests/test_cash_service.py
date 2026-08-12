import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.cash_service import CashService


class CashServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "cash.db"
        conn = sqlite3.connect(self.db)
        conn.executescript(
            """
            CREATE TABLE caixa_aberturas(
                data_caixa TEXT PRIMARY KEY, valor_inicial REAL, responsavel TEXT,
                observacao TEXT, criado_em TEXT
            );
            CREATE TABLE movimentacoes(
                id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT,
                descricao TEXT, valor REAL, data TEXT, status_pagamento TEXT,
                valor_aberto REAL, forma_pagamento TEXT, responsavel TEXT
            );
            CREATE TABLE fechamentos_caixa(
                id INTEGER PRIMARY KEY AUTOINCREMENT, data_caixa TEXT,
                valor_esperado REAL, valor_contado REAL, diferenca REAL,
                responsavel TEXT, observacao TEXT, pdf_path TEXT, criado_em TEXT
            );
            """
        )
        conn.commit()
        conn.close()
        self.service = CashService(lambda: sqlite3.connect(self.db))

    def tearDown(self):
        self.tmp.cleanup()

    def test_opening_and_summary(self):
        self.service.register_opening("2026-08-02", 100, "Ana", "Início", "02/08/2026 08:00:00")
        self.service.register_movement("SUPRIMENTO", 50, "Dinheiro", occurred_at="02/08/2026 09:00:00")
        self.service.register_movement("RETIRADA", 20, "Dinheiro", occurred_at="02/08/2026 10:00:00")
        summary = self.service.daily_summary("02/08/2026")
        self.assertTrue(self.service.has_opening("2026-08-02"))
        self.assertEqual(summary["abertura"], 100)
        self.assertEqual(summary["saldo_esperado"], 130)

    def test_register_movement_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            self.service.register_movement("INEXISTENTE", 10, "Dinheiro")
        with self.assertRaises(ValueError):
            self.service.register_movement("RETIRADA", 0, "Dinheiro")

    def test_save_and_replace_closing(self):
        first = self.service.save_closing("2026-08-02", 100, 90, "Ana")
        self.assertFalse(first.replaced)
        with self.assertRaises(FileExistsError):
            self.service.save_closing("2026-08-02", 100, 100)
        second = self.service.save_closing("2026-08-02", 100, 100, replace_existing=True)
        self.assertTrue(second.replaced)
        self.assertEqual(first.closing_id, second.closing_id)

    def test_movement_type_and_connection_close(self):
        movement_id = self.service.register_movement("PAGAMENTO DE CONTA", 25, "PIX")
        self.assertEqual(self.service.movement_type(movement_id), "PAGAMENTO_CONTA")
        conn = sqlite3.connect(self.db)
        conn.execute("BEGIN IMMEDIATE")
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    unittest.main()
