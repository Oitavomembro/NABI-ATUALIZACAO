import sqlite3
import unittest

from core.global_search import CommandDefinition, GlobalSearchEngine, normalize_search_text


class SharedMemoryDatabase:
    def __init__(self):
        self.uri = "file:nabicode_global_search?mode=memory&cache=shared"
        self.anchor = sqlite3.connect(self.uri, uri=True)
        self._create_schema(self.anchor)

    def connect(self):
        return sqlite3.connect(self.uri, uri=True)

    def close(self):
        self.anchor.close()

    @staticmethod
    def _create_schema(conn):
        conn.executescript(
            """
            CREATE TABLE produtos (
                id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, codigo_barras TEXT,
                preco_venda REAL, estoque_atual REAL, ativo INTEGER
            );
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY, codigo TEXT, numero_ficha INTEGER, nome TEXT,
                cpf TEXT, telefone TEXT, saldo_devedor REAL
            );
            CREATE TABLE fornecedores (
                id INTEGER PRIMARY KEY, nome_fantasia TEXT, razao_social TEXT,
                cnpj TEXT, telefone TEXT, ativo INTEGER
            );
            CREATE TABLE nfe_importacoes (
                id INTEGER PRIMARY KEY, numero TEXT, chave TEXT, fornecedor_nome TEXT,
                fornecedor_cnpj TEXT, status TEXT, data_importacao TEXT
            );
            CREATE TABLE titulos_financeiros (
                id INTEGER PRIMARY KEY, tipo TEXT, pessoa_nome TEXT, documento TEXT,
                descricao TEXT, data_vencimento TEXT, valor_original REAL,
                valor_pago REAL, status TEXT, origem_id TEXT
            );
            """
        )
        conn.execute("INSERT INTO produtos VALUES (1,'P001','CAFÉ TORRADO 500G','7891000000011',19.9,12,1)")
        conn.execute("INSERT INTO clientes VALUES (1,'CLI1',5501,'JOÃO DA SILVA','123.456.789-00','11999999999',80)")
        conn.execute("INSERT INTO fornecedores VALUES (1,'DISTRIBUIDORA SUL','SUL ALIMENTOS LTDA','11222333000144','1133334444',1)")
        conn.execute("INSERT INTO nfe_importacoes VALUES (1,'1234','35260811222333000144550010000012341000012345','DISTRIBUIDORA SUL','11222333000144','CONCLUIDA','2026-08-02 10:00:00')")
        conn.execute("INSERT INTO titulos_financeiros VALUES (1,'RECEBER','JOÃO DA SILVA','PROM-1','PROMISSÓRIA','2026-08-10',100,20,'PARCIAL','V1')")
        conn.commit()


class GlobalSearchEngineTests(unittest.TestCase):
    def setUp(self):
        self.db = SharedMemoryDatabase()
        self.engine = GlobalSearchEngine(
            self.db.connect,
            [CommandDefinition("vendas", "Abrir Vendas", ("pdv", "caixa"))],
        )

    def tearDown(self):
        self.db.close()

    def test_normalize_removes_accents_and_case(self):
        self.assertEqual(normalize_search_text("  Configurações  "), "configuracoes")

    def test_empty_search_returns_commands(self):
        results = self.engine.search("")
        self.assertEqual(results[0].action, "vendas")

    def test_search_product_by_name_without_accent(self):
        results = self.engine.search("cafe")
        product = next(item for item in results if item.kind == "product")
        self.assertEqual(product.payload["product_id"], 1)

    def test_search_product_by_barcode(self):
        results = self.engine.search("7891000000011")
        self.assertTrue(any(item.kind == "product" for item in results))

    def test_search_client(self):
        results = self.engine.search("joao")
        client = next(item for item in results if item.kind == "client")
        self.assertEqual(client.payload["client_id"], 1)

    def test_search_supplier_and_nfe(self):
        supplier_results = self.engine.search("distribuidora")
        self.assertTrue(any(item.kind == "supplier" for item in supplier_results))
        nfe_results = self.engine.search("1234")
        self.assertTrue(any(item.kind == "nfe" for item in nfe_results))

    def test_search_financial(self):
        results = self.engine.search("promissoria")
        title = next(item for item in results if item.kind == "financial")
        self.assertEqual(title.payload["title_id"], 1)

    def test_search_command_keyword(self):
        results = self.engine.search("pdv")
        self.assertTrue(any(item.action == "vendas" for item in results))


if __name__ == "__main__":
    unittest.main()
