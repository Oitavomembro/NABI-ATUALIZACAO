import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.movement_service import MovementService


class MovementServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        conn = sqlite3.connect(self.db)
        conn.executescript(
            """
            CREATE TABLE clientes(id INTEGER PRIMARY KEY,nome TEXT,saldo_devedor REAL DEFAULT 0);
            CREATE TABLE movimentacoes(
                id INTEGER PRIMARY KEY,cliente_id INTEGER,tipo TEXT,descricao TEXT,valor REAL,
                data TEXT,forma_pagamento TEXT
            );
            CREATE TABLE historico_clientes(
                id INTEGER PRIMARY KEY,cliente_id INTEGER,evento TEXT,detalhes TEXT,data TEXT
            );
            INSERT INTO clientes(id,nome,saldo_devedor) VALUES(1,'CLIENTE',100);
            INSERT INTO movimentacoes(id,cliente_id,tipo,descricao,valor,data,forma_pagamento)
            VALUES(10,1,'COMPRA','ITEM',100,'01/08/2026','DINHEIRO');
            """
        )
        conn.commit()
        conn.close()
        self.service = MovementService(lambda: sqlite3.connect(self.db))

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_returns_complete_record(self):
        item = self.service.get(10)
        self.assertIsNotNone(item)
        self.assertEqual(item.customer_name, "CLIENTE")
        self.assertEqual(item.payment_method, "DINHEIRO")

    def test_update_purchase_adjusts_balance_and_history(self):
        updated = self.service.update(10, "ITEM EDITADO", 130)
        self.assertEqual(updated.value, 130)
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 130)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM historico_clientes").fetchone()[0], 1)
        finally:
            conn.close()

    def test_update_payment_uses_inverse_balance_delta(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE movimentacoes SET tipo='PAGAMENTO',valor=20 WHERE id=10")
        conn.execute("UPDATE clientes SET saldo_devedor=80 WHERE id=1")
        conn.commit(); conn.close()
        self.service.update(10, "PAGAMENTO EDITADO", 30)
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 70)
        finally:
            conn.close()

    def test_failure_rolls_back_balance_and_movement(self):
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE historico_clientes")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.OperationalError):
            self.service.update(10, "FALHA", 150)
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 100)
            self.assertEqual(conn.execute("SELECT descricao,valor FROM movimentacoes WHERE id=10").fetchone(), ("ITEM", 100.0))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
