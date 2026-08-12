import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from services.cash_service import CashService
from database.product_decimal_migration import ProductDecimalMigration


class PDVCashDecimalPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE produtos(id INTEGER PRIMARY KEY, preco_venda REAL);
        CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT, descricao TEXT, valor REAL, data TEXT, status_pagamento TEXT, valor_aberto REAL, forma_pagamento TEXT, responsavel TEXT);
        CREATE TABLE parcelas(id INTEGER PRIMARY KEY, valor_parcela REAL, valor_pago REAL);
        CREATE TABLE clientes(id INTEGER PRIMARY KEY, saldo_devedor REAL);
        CREATE TABLE caixa_aberturas(id INTEGER PRIMARY KEY AUTOINCREMENT, data_caixa TEXT UNIQUE, valor_inicial REAL, responsavel TEXT, observacao TEXT, criado_em TEXT);
        CREATE TABLE fechamentos_caixa(id INTEGER PRIMARY KEY AUTOINCREMENT, data_caixa TEXT, valor_esperado REAL, valor_contado REAL, diferenca REAL, responsavel TEXT, observacao TEXT, pdf_path TEXT, criado_em TEXT);
        """)
        ProductDecimalMigration.migrate_connection(conn)
        conn.commit(); conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def factory(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_cash_persists_canonical_text(self):
        service = CashService(self.factory)
        service.register_opening("2026-08-05", Decimal("0.1000000000000000001"))
        service.register_movement("SUPRIMENTO", Decimal("0.2000000000000000002"), "PIX")
        conn = self.factory()
        opening = conn.execute("SELECT valor_inicial_decimal, typeof(valor_inicial_decimal) FROM caixa_aberturas").fetchone()
        movement = conn.execute("SELECT valor_decimal, typeof(valor_decimal) FROM movimentacoes").fetchone()
        conn.close()
        self.assertEqual(opening[0], "0.1000000000000000001")
        self.assertEqual(opening[1], "text")
        self.assertEqual(movement[0], "0.2000000000000000002")
        self.assertEqual(movement[1], "text")

    def test_cash_summary_prefers_canonical_values(self):
        service = CashService(self.factory)
        service.register_opening("2026-08-05", Decimal("0.10"), created_at="05/08/2026 08:00:00")
        service.register_movement("SUPRIMENTO", Decimal("0.20"), "PIX", occurred_at="05/08/2026 09:00:00")
        summary = service.daily_summary("05/08/2026")
        self.assertEqual(summary["abertura"], Decimal("0.1"))
        self.assertEqual(summary["suprimentos"], Decimal("0.2"))
        self.assertEqual(summary["saldo_esperado"], Decimal("0.3"))


if __name__ == "__main__":
    unittest.main()
