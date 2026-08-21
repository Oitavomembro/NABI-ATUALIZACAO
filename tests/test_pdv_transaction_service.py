import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from services.pdv_service import PDVService
from services.pdv_transaction_service import PDVTransactionService
from services.fiscal_outbox_service import FiscalOutboxService


class FakeStockService:
    def baixar_itens_venda_na_transacao(self, conn, items, *, venda_id, usuario):
        for item in items:
            if item.get("produto_id") in (None, ""):
                continue
            conn.execute("UPDATE produtos SET estoque_atual=estoque_atual-? WHERE id=?", (item["qtd"], item["produto_id"]))
            conn.execute("INSERT INTO estoque_movimentacoes(produto_id, tipo, quantidade, origem, origem_id) VALUES (?, 'SAIDA', ?, 'VENDA', ?)", (item["produto_id"], item["qtd"], venda_id))

    def estornar_venda_na_transacao(self, conn, venda_id, *, usuario):
        rows = conn.execute("SELECT produto_id, quantidade FROM estoque_movimentacoes WHERE origem='VENDA' AND origem_id=?", (venda_id,)).fetchall()
        for produto_id, quantidade in rows:
            conn.execute("UPDATE produtos SET estoque_atual=estoque_atual+? WHERE id=?", (quantidade, produto_id))


class FakeFinanceService:
    def registrar_venda_crediario_transacao(self, conn, **kwargs):
        conn.execute("INSERT INTO financeiro_titulos(tipo, origem, origem_id, valor, status) VALUES ('RECEBER','VENDA',?,?,'ABERTO')", (kwargs["venda_id"], kwargs["valor"]))

    def cancelar_titulos_origem_transacao(self, conn, *, origem_id, **kwargs):
        conn.execute("UPDATE financeiro_titulos SET status='CANCELADO' WHERE origem='VENDA' AND origem_id=?", (origem_id,))


class PDVTransactionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "pdv.db"
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE clientes(id INTEGER PRIMARY KEY, nome TEXT, saldo_devedor REAL DEFAULT 0);
            CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT, descricao TEXT, valor REAL, data TEXT, vencimento TEXT, status_pagamento TEXT, valor_aberto REAL, forma_pagamento TEXT);
            CREATE TABLE parcelas(id INTEGER PRIMARY KEY AUTOINCREMENT, movimentacao_id INTEGER, numero_parcela INTEGER, valor_parcela REAL, vencimento TEXT, status TEXT, valor_pago REAL, data_pagamento TEXT, atraso_registrado INTEGER, dados_confiaveis INTEGER);
            CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
            CREATE TABLE produtos(id INTEGER PRIMARY KEY, estoque_atual REAL);
            CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, tipo TEXT, quantidade REAL, origem TEXT, origem_id INTEGER);
            CREATE TABLE financeiro_titulos(id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, origem TEXT, origem_id INTEGER, valor REAL, status TEXT);
            INSERT INTO clientes(id,nome,saldo_devedor) VALUES (1,'CLIENTE',0);
            INSERT INTO produtos(id,estoque_atual) VALUES (1,10);
        """)
        conn.commit(); conn.close()
        factory = lambda: sqlite3.connect(self.db)
        self.pdv = PDVService(factory)
        self.service = PDVTransactionService(factory, estoque_service=FakeStockService(), financeiro_service=FakeFinanceService(), pdv_service=self.pdv)
        self.item = {"produto_id": 1, "item": "PRODUTO", "qtd": 2, "preco": 5, "subtotal": 10}

    def tearDown(self):
        self.tmp.cleanup()

    def test_finaliza_venda_paga_atomicamente(self):
        result = self.service.finalize_sale(customer_id=1, customer_name="CLIENTE", items=[self.item], payments=[{"forma":"DINHEIRO","valor":10}], received=10, change=0, user="admin")
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("SELECT status_pagamento FROM movimentacoes WHERE id=?", (result.sale_id,)).fetchone()[0], "PAGO")
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE id=1").fetchone()[0], 8)
        self.assertIsNotNone(conn.execute("SELECT valor FROM configuracoes WHERE chave=?", (f"pdv_pagamentos_venda_{result.sale_id}",)).fetchone())
        conn.close()

    def test_crediario_cria_titulo_e_saldo(self):
        result = self.service.finalize_sale(customer_id=1, customer_name="CLIENTE", items=[self.item], payments=[{"forma":"CREDIARIO","valor":10}], received=10, change=0, user="admin")
        conn = sqlite3.connect(self.db)
        self.assertEqual(result.status, "PENDENTE")
        self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 10)
        self.assertEqual(conn.execute("SELECT status FROM financeiro_titulos WHERE origem_id=?", (result.sale_id,)).fetchone()[0], "ABERTO")
        conn.close()

    def test_falha_no_estoque_reverte_toda_venda(self):
        class BrokenStock(FakeStockService):
            def baixar_itens_venda_na_transacao(self, *args, **kwargs):
                raise ValueError("sem estoque")
        service = PDVTransactionService(lambda: sqlite3.connect(self.db), estoque_service=BrokenStock(), financeiro_service=FakeFinanceService(), pdv_service=self.pdv)
        with self.assertRaisesRegex(ValueError, "sem estoque"):
            service.finalize_sale(customer_id=1, customer_name="CLIENTE", items=[self.item], payments=[{"forma":"CREDIARIO","valor":10}], received=10, change=0, user="admin")
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE id=1").fetchone()[0], 10)
        conn.close()

    def test_falha_depois_da_baixa_de_estoque_reverte_toda_venda(self):
        class BrokenAfterStock(FakeStockService):
            def baixar_itens_venda_na_transacao(self, conn, items, *, venda_id, usuario):
                super().baixar_itens_venda_na_transacao(
                    conn, items, venda_id=venda_id, usuario=usuario
                )
                raise RuntimeError("falha depois do estoque")

        service = PDVTransactionService(
            lambda: sqlite3.connect(self.db),
            estoque_service=BrokenAfterStock(),
            financeiro_service=FakeFinanceService(),
            pdv_service=self.pdv,
        )
        with self.assertRaisesRegex(RuntimeError, "depois do estoque"):
            service.finalize_sale(
                customer_id=1, customer_name="CLIENTE", items=[self.item],
                payments=[{"forma": "CREDIARIO", "valor": 10}],
                received=10, change=0, user="admin",
            )
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM estoque_movimentacoes").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM financeiro_titulos").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE id=1").fetchone()[0], 10)
        self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 0)
        conn.close()

    def test_venda_comercial_nao_cria_documento_nem_outbox(self):
        conn = sqlite3.connect(self.db)
        FiscalOutboxService.ensure_schema(conn)
        conn.commit(); conn.close()
        self.service.finalize_sale(
            customer_id=1, customer_name="CLIENTE", items=[self.item],
            payments=[{"forma": "DINHEIRO", "valor": 10}],
            received=10, change=0, user="admin",
        )
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM fiscal_outbox").fetchone()[0], 0)
        self.assertFalse(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fiscal_sale_documents'"
        ).fetchone())
        conn.close()

    def test_lista_somente_vendas_do_dia_com_estado_fiscal(self):
        conn = sqlite3.connect(self.db)
        conn.execute(
            "CREATE TABLE fiscal_sale_documents("
            "sale_id INTEGER UNIQUE,status TEXT,model TEXT,access_key TEXT,protocol TEXT)"
        )
        conn.execute(
            "INSERT INTO movimentacoes(cliente_id,tipo,descricao,valor,data,status_pagamento) "
            "VALUES(1,'COMPRA','VENDA DE HOJE',15,'20/08/2026 10:00','PAGO')"
        )
        today_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO fiscal_sale_documents VALUES(?,?,?,?,?)",
            (today_id, "AUTORIZADA", "65", "29" + "1" * 42, "123"),
        )
        conn.execute(
            "INSERT INTO movimentacoes(cliente_id,tipo,descricao,valor,data,status_pagamento) "
            "VALUES(1,'COMPRA','VENDA ANTIGA',20,'19/08/2026 18:00','PAGO')"
        )
        conn.commit(); conn.close()

        rows = self.service.list_sales_for_day(day=datetime(2026, 8, 20))

        self.assertEqual([row["id"] for row in rows], [today_id])
        self.assertEqual(rows[0]["fiscal_status"], "AUTORIZADA")
        self.assertEqual(rows[0]["fiscal_model"], "65")

    def test_vinculo_fiscal_participa_da_mesma_transacao_da_venda(self):
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE fiscal_sale_documents(sale_id INTEGER UNIQUE, access_key TEXT)")
        conn.commit(); conn.close()

        result = self.service.finalize_sale(
            customer_id=1, customer_name="CLIENTE", items=[self.item],
            payments=[{"forma": "DINHEIRO", "valor": 10}], received=10, change=0,
            user="admin",
            after_sale_in_transaction=lambda connection, sale_id: connection.execute(
                "INSERT INTO fiscal_sale_documents(sale_id,access_key) VALUES(?,?)",
                (sale_id, "29" + "0" * 42),
            ),
        )
        conn = sqlite3.connect(self.db)
        self.assertEqual(
            conn.execute("SELECT sale_id FROM fiscal_sale_documents").fetchone()[0],
            result.sale_id,
        )
        conn.close()

    def test_lista_vendas_por_periodo_em_datas_iso_e_legada(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento) VALUES('COMPRA','ISO',10,'2026-08-10 12:00','PAGO')")
        conn.execute("INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento) VALUES('COMPRA','LEGADA',20,'11/08/2026 13:00','PAGO')")
        conn.execute("INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento) VALUES('COMPRA','FORA',30,'12/08/2026 13:00','PAGO')")
        conn.commit(); conn.close()
        rows = self.service.list_sales_for_period(start_date="2026-08-10", end_date="2026-08-11")
        self.assertEqual({row["descricao"] for row in rows}, {"ISO", "LEGADA"})

    def test_falha_ao_vincular_documento_fiscal_reverte_venda_inteira(self):
        def fail_link(_connection, _sale_id):
            raise RuntimeError("falha no vínculo fiscal")

        with self.assertRaisesRegex(RuntimeError, "vínculo fiscal"):
            self.service.finalize_sale(
                customer_id=1, customer_name="CLIENTE", items=[self.item],
                payments=[{"forma": "DINHEIRO", "valor": 10}], received=10, change=0,
                user="admin", after_sale_in_transaction=fail_link,
            )
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE id=1").fetchone()[0], 10)
        conn.close()

    def test_falha_depois_do_movimento_financeiro_reverte_saldo_e_venda(self):
        class BrokenAfterFinance(FakeFinanceService):
            def registrar_venda_crediario_transacao(self, conn, **kwargs):
                super().registrar_venda_crediario_transacao(conn, **kwargs)
                raise RuntimeError("falha depois do financeiro")

        service = PDVTransactionService(
            lambda: sqlite3.connect(self.db),
            estoque_service=FakeStockService(),
            financeiro_service=BrokenAfterFinance(),
            pdv_service=self.pdv,
        )
        with self.assertRaisesRegex(RuntimeError, "depois do financeiro"):
            service.finalize_sale(
                customer_id=1, customer_name="CLIENTE", items=[self.item],
                payments=[{"forma": "CREDIARIO", "valor": 10}],
                received=10, change=0, user="admin",
            )
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM financeiro_titulos").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE id=1").fetchone()[0], 10)
        conn.close()


    def test_item_avulso_nao_movimenta_estoque_e_fica_identificado(self):
        avulso = {
            "produto_id": None,
            "item": "ANTENA",
            "qtd": 1,
            "preco": 150,
            "subtotal": 150,
            "item_avulso": True,
            "controla_estoque": False,
        }
        result = self.service.finalize_sale(
            customer_id=1,
            customer_name="CLIENTE",
            items=[avulso],
            payments=[{"forma": "DINHEIRO", "valor": 150}],
            received=150,
            change=0,
            user="admin",
        )
        conn = sqlite3.connect(self.db)
        descricao = conn.execute("SELECT descricao FROM movimentacoes WHERE id=?", (result.sale_id,)).fetchone()[0]
        self.assertIn("ANTENA", descricao)
        self.assertIn("AVULSO/SEM ESTOQUE", descricao)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE id=1").fetchone()[0], 10)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM estoque_movimentacoes").fetchone()[0], 0)
        conn.close()

    def test_cancelamento_reverte_estoque_financeiro_e_saldo(self):
        result = self.service.finalize_sale(customer_id=1, customer_name="CLIENTE", items=[self.item], payments=[{"forma":"CREDIARIO","valor":10}], received=10, change=0, user="admin")
        self.service.cancel_sale(result.sale_id, user="admin")
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("SELECT status_pagamento FROM movimentacoes WHERE id=?", (result.sale_id,)).fetchone()[0], "CANCELADO")
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE id=1").fetchone()[0], 10)
        self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT status FROM financeiro_titulos WHERE origem_id=?", (result.sale_id,)).fetchone()[0], "CANCELADO")
        conn.close()

    def test_falha_na_protecao_fiscal_reverte_cancelamento_local(self):
        result = self.service.finalize_sale(
            customer_id=1, customer_name="CLIENTE", items=[self.item],
            payments=[{"forma":"DINHEIRO","valor":10}], received=10, change=0, user="admin"
        )
        with self.assertRaisesRegex(ValueError, "documento autorizado"):
            self.service.cancel_sale(
                result.sale_id, user="admin",
                before_cancel_commit=lambda _conn, _sale_id: (_ for _ in ()).throw(
                    ValueError("documento autorizado")
                ),
            )
        conn = sqlite3.connect(self.db)
        self.assertNotEqual(conn.execute("SELECT status_pagamento FROM movimentacoes WHERE id=?", (result.sale_id,)).fetchone()[0], "CANCELADO")
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE id=1").fetchone()[0], 8)
        conn.close()

    def test_cancelar_venda_paga_nao_reduz_saldo_de_outra_venda_crediario(self):
        self.service.finalize_sale(
            customer_id=1, customer_name="CLIENTE", items=[self.item],
            payments=[{"forma": "CREDIARIO", "valor": 10}],
            received=10, change=0, user="admin",
        )
        paid = self.service.finalize_sale(
            customer_id=1, customer_name="CLIENTE", items=[self.item],
            payments=[{"forma": "DINHEIRO", "valor": 10}],
            received=10, change=0, user="admin",
        )
        self.service.cancel_sale(paid.sale_id, user="admin")
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0], 10)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
