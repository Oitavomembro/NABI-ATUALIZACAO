from __future__ import annotations

import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import DatabaseManager, ProductDecimalMigration
from repositories import CadastroAuxiliarRepository, CategoriaRepository, ProdutoRepository
from services import ProductApplicationService, ProductFormData, ProdutoService

SCHEMA = """
CREATE TABLE categorias_produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT UNIQUE,ativo INTEGER DEFAULT 1,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE marcas_produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT UNIQUE,ativo INTEGER DEFAULT 1,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE fornecedores(id INTEGER PRIMARY KEY AUTOINCREMENT,razao_social TEXT,nome_fantasia TEXT UNIQUE,cnpj TEXT,telefone TEXT,email TEXT,ativo INTEGER DEFAULT 1,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE unidades_medida(id INTEGER PRIMARY KEY AUTOINCREMENT,sigla TEXT UNIQUE,descricao TEXT,permite_fracionado INTEGER DEFAULT 0,ativo INTEGER DEFAULT 1,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,codigo TEXT UNIQUE,nome TEXT,preco_venda REAL DEFAULT 0,preco_custo REAL DEFAULT 0,despesas_percentual REAL DEFAULT 0,margem_lucro REAL DEFAULT 0,categoria_id INTEGER,marca_id INTEGER,fornecedor_id INTEGER,unidade_id INTEGER,unidade_compra_id INTEGER,fator_conversao REAL DEFAULT 1,tipo_produto TEXT DEFAULT 'MERCADORIA',controla_estoque INTEGER DEFAULT 1,participa_xml INTEGER DEFAULT 1,codigo_barras TEXT DEFAULT '',ncm TEXT DEFAULT '',cest TEXT DEFAULT '',cfop TEXT DEFAULT '',estoque_atual REAL DEFAULT 0,estoque_minimo REAL DEFAULT 0,permite_estoque_negativo INTEGER DEFAULT 0,ativo INTEGER DEFAULT 1,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE historico_precos_produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,preco_anterior REAL DEFAULT 0,preco_novo REAL DEFAULT 0,custo REAL DEFAULT 0,margem_percentual REAL DEFAULT 0,motivo TEXT,data TEXT);
"""

class FakeEstoque:
    def __init__(self, database):
        self.database = database

class ExactDecimalPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "decimal.db"
        con = sqlite3.connect(self.path)
        con.executescript(SCHEMA)
        con.close()
        self.db = DatabaseManager(self.path)
        ProductDecimalMigration(self.db).run()
        repo = ProdutoRepository(self.db)
        service = ProdutoService(repo, CategoriaRepository(self.db), CadastroAuxiliarRepository(self.db))
        self.app = ProductApplicationService(service, FakeEstoque(self.db))
        self.service = service

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_decimal_is_stored_in_text_shadow_column(self):
        value = Decimal("0.1000000000000000001")
        product_id = self.service.salvar(codigo="D1", nome="Decimal", preco_venda=value, categoria_id=None, tipo_produto="MERCADORIA")
        con = sqlite3.connect(self.path)
        row = con.execute("SELECT preco_venda_decimal, typeof(preco_venda_decimal), typeof(preco_venda) FROM produtos WHERE id=?", (product_id,)).fetchone()
        con.close()
        self.assertEqual("0.1000000000000000001", row[0])
        self.assertEqual("text", row[1])
        self.assertEqual("real", row[2])
        self.assertEqual(value, self.service.buscar(product_id)["preco_venda"])

    def test_legacy_real_value_is_migrated_idempotently(self):
        con = sqlite3.connect(self.path)
        con.execute("INSERT INTO produtos(codigo,nome,preco_venda,tipo_produto,criado_em,atualizado_em) VALUES('L1','Legado',12.34,'MERCADORIA','','')")
        con.commit(); con.close()
        ProductDecimalMigration(self.db).run()
        ProductDecimalMigration(self.db).run()
        con = sqlite3.connect(self.path)
        row = con.execute("SELECT preco_venda_decimal FROM produtos WHERE codigo='L1'").fetchone()
        con.close()
        self.assertEqual("12.34", row[0])

    def test_complete_application_flow_preserves_decimal_and_history(self):
        command = self.app.criar_comando(ProductFormData(codigo="I1", nome="Integrado", preco_venda="1234,567890123456789", preco_custo="100,01", despesas_percentual="2,5", margem_lucro="20", tipo_produto="MERCADORIA", categoria_id=None))
        result = self.app.salvar(command)
        product = self.service.buscar(result.produto_id)
        state = self.app.criar_estado_formulario(product, categorias={}, marcas={}, fornecedores={}, unidades={})
        history = self.service.listar_historico(result.produto_id)
        self.assertEqual(Decimal("1234.567890123456789"), product["preco_venda"])
        self.assertEqual("1234,567890123456789", state.preco_venda)
        self.assertEqual(Decimal("1234.567890123456789"), history[0]["preco_novo"])
