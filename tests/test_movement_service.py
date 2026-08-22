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
                data TEXT,forma_pagamento TEXT,status_pagamento TEXT
            );
            CREATE TABLE historico_clientes(
                id INTEGER PRIMARY KEY,cliente_id INTEGER,evento TEXT,detalhes TEXT,data TEXT
            );
            CREATE TABLE parcelas(id INTEGER PRIMARY KEY,movimentacao_id INTEGER,status TEXT);
            CREATE TABLE estoque_movimentacoes(
                id INTEGER PRIMARY KEY,origem TEXT,origem_id TEXT
            );
            CREATE TABLE fiscal_sale_documents(id INTEGER PRIMARY KEY,sale_id INTEGER);
            CREATE TABLE titulos_financeiros(
                id INTEGER PRIMARY KEY,origem TEXT,origem_id TEXT,status TEXT,valor_pago REAL
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

    def assert_integrated_edit_is_blocked(
        self, *, expected_balance=100, expected_description="ITEM", expected_value=100.0
    ):
        with self.assertRaisesRegex(ValueError, "não pode ser editado genericamente"):
            self.service.update(10, "ITEM EDITADO", 130)
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], expected_balance)
            self.assertEqual(
                conn.execute("SELECT descricao,valor FROM movimentacoes WHERE id=10").fetchone(),
                (expected_description, expected_value),
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM historico_clientes").fetchone()[0], 0)
        finally:
            conn.close()

    def test_bloqueia_venda_crediaria(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO titulos_financeiros VALUES(1,'VENDA','10','ABERTO',0)")
        conn.commit(); conn.close()
        self.assert_integrated_edit_is_blocked()

    def test_bloqueia_venda_com_parcelas(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO parcelas VALUES(1,10,'PENDENTE')")
        conn.commit(); conn.close()
        self.assert_integrated_edit_is_blocked()

    def test_bloqueia_venda_paga_ou_parcial(self):
        for status in ("PAGO", "PARCIAL"):
            conn = sqlite3.connect(self.db)
            conn.execute("UPDATE movimentacoes SET status_pagamento=? WHERE id=10", (status,))
            conn.commit(); conn.close()
            self.assert_integrated_edit_is_blocked()

    def test_bloqueia_movimento_integrado_ao_estoque(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE movimentacoes SET cliente_id=NULL,tipo='AJUSTE' WHERE id=10")
        conn.execute("INSERT INTO estoque_movimentacoes VALUES(1,'VENDA','10')")
        conn.commit(); conn.close()
        self.assert_integrated_edit_is_blocked()

    def test_bloqueia_movimento_fiscal(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE movimentacoes SET cliente_id=NULL,tipo='AJUSTE' WHERE id=10")
        conn.execute("INSERT INTO fiscal_sale_documents VALUES(1,10)")
        conn.commit(); conn.close()
        self.assert_integrated_edit_is_blocked()

    def test_bloqueia_pagamento_vinculado_ao_cliente(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE movimentacoes SET tipo='PAGAMENTO',valor=20 WHERE id=10")
        conn.execute("UPDATE clientes SET saldo_devedor=80 WHERE id=1")
        conn.commit(); conn.close()
        self.assert_integrated_edit_is_blocked(expected_balance=80, expected_value=20.0)

    def test_permite_somente_movimento_independente(self):
        conn = sqlite3.connect(self.db)
        conn.execute(
            "UPDATE movimentacoes SET cliente_id=NULL,tipo='AJUSTE',descricao='AJUSTE LIVRE' WHERE id=10"
        )
        conn.commit(); conn.close()
        updated = self.service.update(10, "AJUSTE INDEPENDENTE", 150)
        self.assertEqual(updated.value, 150)
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 100)
            self.assertEqual(
                conn.execute("SELECT descricao,valor FROM movimentacoes WHERE id=10").fetchone(),
                ("AJUSTE INDEPENDENTE", 150.0),
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
