import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import DatabaseManager
from repositories import FinanceiroRepository
from services import FinanceiroService
from services.pdv_service import PDVService
from services.pdv_transaction_service import PDVTransactionService
from tests.test_pdv_transaction_service import FakeFinanceService, FakeStockService
from tests.test_financeiro_service import SCHEMA


class CancelamentoPDVDecimalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "pdv_decimal.db"
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE clientes(id INTEGER PRIMARY KEY, nome TEXT, saldo_devedor REAL DEFAULT 0, saldo_devedor_decimal TEXT);
            CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT, descricao TEXT, valor REAL, valor_decimal TEXT, data TEXT, vencimento TEXT, status_pagamento TEXT, valor_aberto REAL, valor_aberto_decimal TEXT, forma_pagamento TEXT);
            CREATE TABLE parcelas(id INTEGER PRIMARY KEY AUTOINCREMENT, movimentacao_id INTEGER, numero_parcela INTEGER, valor_parcela REAL, valor_parcela_decimal TEXT, vencimento TEXT, status TEXT, valor_pago REAL, valor_pago_decimal TEXT, data_pagamento TEXT, atraso_registrado INTEGER, dados_confiaveis INTEGER);
            CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
            CREATE TABLE produtos(id INTEGER PRIMARY KEY, estoque_atual REAL);
            CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, tipo TEXT, quantidade REAL, origem TEXT, origem_id INTEGER);
            CREATE TABLE financeiro_titulos(id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, origem TEXT, origem_id INTEGER, valor REAL, status TEXT);
            INSERT INTO clientes(id,nome,saldo_devedor,saldo_devedor_decimal) VALUES (1,'CLIENTE',0,'0');
            INSERT INTO produtos(id,estoque_atual) VALUES (1,10);
        """)
        conn.commit()
        conn.close()
        factory = lambda: sqlite3.connect(self.db)
        self.service = PDVTransactionService(
            factory,
            estoque_service=FakeStockService(),
            financeiro_service=FakeFinanceService(),
            pdv_service=PDVService(factory),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_cancelamento_usa_valor_canonico_e_zera_saldo_canonico(self):
        item = {"produto_id": 1, "item": "PRODUTO", "qtd": 1, "preco": Decimal("0.1000000000000000001"), "subtotal": Decimal("0.1000000000000000001")}
        result = self.service.finalize_sale(
            customer_id=1, customer_name="CLIENTE", items=[item],
            payments=[{"forma": "CREDIARIO", "valor": Decimal("0.10")}],
            received=Decimal("0.10"), change=0, user="admin",
        )
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE movimentacoes SET valor=999, valor_decimal='0.10' WHERE id=?", (result.sale_id,))
        conn.execute("UPDATE clientes SET saldo_devedor=999, saldo_devedor_decimal='0.10' WHERE id=1")
        conn.commit(); conn.close()

        self.service.cancel_sale(result.sale_id, user="admin")

        conn = sqlite3.connect(self.db)
        saldo = conn.execute("SELECT saldo_devedor,saldo_devedor_decimal FROM clientes WHERE id=1").fetchone()
        movimento = conn.execute("SELECT valor_aberto,valor_aberto_decimal,status_pagamento FROM movimentacoes WHERE id=?", (result.sale_id,)).fetchone()
        conn.close()
        self.assertEqual(Decimal(str(saldo[0])), Decimal("0"))
        self.assertEqual(Decimal(saldo[1]), Decimal("0"))
        self.assertEqual(Decimal(str(movimento[0])), Decimal("0"))
        self.assertEqual(Decimal(movimento[1]), Decimal("0"))
        self.assertEqual(movimento[2], "CANCELADO")


class EstornoFinanceiroDecimalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "financeiro_decimal.db")
        conn = sqlite3.connect(self.db)
        conn.executescript(SCHEMA + """
            ALTER TABLE movimentacoes ADD COLUMN valor_aberto_decimal TEXT;
            CREATE TABLE clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT,saldo_devedor REAL DEFAULT 0,saldo_devedor_decimal TEXT);
            CREATE TABLE parcelas(id INTEGER PRIMARY KEY AUTOINCREMENT,movimentacao_id INTEGER,numero_parcela INTEGER,valor_parcela REAL,valor_parcela_decimal TEXT,vencimento TEXT,status TEXT DEFAULT 'PENDENTE',valor_pago REAL DEFAULT 0,valor_pago_decimal TEXT,data_pagamento TEXT DEFAULT '',atraso_registrado INTEGER DEFAULT 0);
        """)
        conn.close()
        self.database = DatabaseManager(self.db)
        self.repo = FinanceiroRepository(self.database)
        self.service = FinanceiroService(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pagamento_e_estorno_sincronizam_movimento_parcela_cliente(self):
        with self.database.session(write=True) as conn:
            cliente_id = conn.execute("INSERT INTO clientes(nome,saldo_devedor,saldo_devedor_decimal) VALUES('CLIENTE',100,'100')").lastrowid
            venda_id = conn.execute("INSERT INTO movimentacoes(cliente_id,tipo,valor,status_pagamento,valor_aberto,valor_aberto_decimal) VALUES(?,'COMPRA',100,'PENDENTE',100,'100')", (cliente_id,)).lastrowid
            parcela_id = conn.execute("INSERT INTO parcelas(movimentacao_id,numero_parcela,valor_parcela,valor_parcela_decimal,vencimento,status,valor_pago,valor_pago_decimal) VALUES(?,1,100,'100','2026-08-01','PENDENTE',0,'0')", (venda_id,)).lastrowid
            titulo_id = self.service.registrar_venda_crediario_transacao(conn, venda_id=venda_id, cliente_id=cliente_id, cliente_nome='CLIENTE', valor=100, data_vencimento='2026-08-01')

        pagamento = self.service.pagar(titulo_id, Decimal("40.00"), forma_pagamento="PIX", data_pagamento="2026-08-10")
        with self.database.session() as conn:
            mov = conn.execute("SELECT valor_aberto,valor_aberto_decimal FROM movimentacoes WHERE id=?", (venda_id,)).fetchone()
            par = conn.execute("SELECT valor_pago,valor_pago_decimal FROM parcelas WHERE id=?", (parcela_id,)).fetchone()
            cli = conn.execute("SELECT saldo_devedor,saldo_devedor_decimal FROM clientes WHERE id=?", (cliente_id,)).fetchone()
        self.assertEqual(Decimal(str(mov[0])), Decimal("60")); self.assertEqual(Decimal(mov[1]), Decimal("60"))
        self.assertEqual(Decimal(str(par[0])), Decimal("40")); self.assertEqual(Decimal(par[1]), Decimal("40"))
        self.assertEqual(Decimal(str(cli[0])), Decimal("60")); self.assertEqual(Decimal(cli[1]), Decimal("60"))

        self.service.estornar_pagamento(pagamento.pagamento_id, usuario="gerente")
        with self.database.session() as conn:
            mov = conn.execute("SELECT valor_aberto,valor_aberto_decimal FROM movimentacoes WHERE id=?", (venda_id,)).fetchone()
            par = conn.execute("SELECT valor_pago,valor_pago_decimal FROM parcelas WHERE id=?", (parcela_id,)).fetchone()
            cli = conn.execute("SELECT saldo_devedor,saldo_devedor_decimal FROM clientes WHERE id=?", (cliente_id,)).fetchone()
        self.assertEqual(Decimal(str(mov[0])), Decimal("100")); self.assertEqual(Decimal(mov[1]), Decimal("100"))
        self.assertEqual(Decimal(str(par[0])), Decimal("0")); self.assertEqual(Decimal(par[1]), Decimal("0"))
        self.assertEqual(Decimal(str(cli[0])), Decimal("100")); self.assertEqual(Decimal(cli[1]), Decimal("100"))


if __name__ == "__main__":
    unittest.main()
