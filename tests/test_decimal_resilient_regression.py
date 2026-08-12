import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import DatabaseManager
from repositories import ProdutoRepository, CompraRepository


class DecimalResilientRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/"db.sqlite"
        self.db=DatabaseManager(self.path)
        with self.db.session(write=True) as c:
            c.executescript("""
            CREATE TABLE produtos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,codigo TEXT,nome TEXT,
                preco_venda REAL,preco_custo REAL,despesas_percentual REAL,margem_lucro REAL,fator_conversao REAL,
                preco_venda_decimal TEXT,preco_custo_decimal TEXT,despesas_percentual_decimal TEXT,margem_lucro_decimal TEXT,fator_conversao_decimal TEXT,
                categoria_id INTEGER,marca_id INTEGER,fornecedor_id INTEGER,unidade_id INTEGER,unidade_compra_id INTEGER,
                tipo_produto TEXT,controla_estoque INTEGER,participa_xml INTEGER,ativo INTEGER,
                codigo_barras TEXT DEFAULT '',ncm TEXT DEFAULT '',cest TEXT DEFAULT '',cfop TEXT DEFAULT '',
                estoque_atual REAL DEFAULT 0,estoque_minimo REAL DEFAULT 0,permite_estoque_negativo INTEGER DEFAULT 0
            );
            CREATE TABLE categorias_produtos(id INTEGER PRIMARY KEY,nome TEXT);
            CREATE TABLE marcas_produtos(id INTEGER PRIMARY KEY,nome TEXT);
            CREATE TABLE fornecedores(id INTEGER PRIMARY KEY,nome_fantasia TEXT);
            CREATE TABLE unidades_medida(id INTEGER PRIMARY KEY,sigla TEXT);
            """)
            c.execute("""INSERT INTO produtos(codigo,nome,preco_venda,preco_custo,despesas_percentual,margem_lucro,fator_conversao,preco_venda_decimal,preco_custo_decimal,despesas_percentual_decimal,margem_lucro_decimal,fator_conversao_decimal,tipo_produto,controla_estoque,participa_xml,ativo) VALUES('1','TESTE',20,10,0,100,1,'','abc','0','100','1','PRODUTO',1,1,1)""")
    def tearDown(self): self.tmp.cleanup()
    def test_product_repository_falls_back_from_empty_and_invalid_canonical(self):
        item=ProdutoRepository(self.db).buscar_por_id(1)
        self.assertEqual(item['preco_venda'],Decimal('20.0'))
        self.assertEqual(item['preco_custo'],Decimal('10.0'))
    def test_purchase_repository_falls_back_from_invalid_canonical(self):
        item=CompraRepository(self.db).buscar_produto(1)
        self.assertEqual(item['preco_custo'],Decimal('10.0'))
