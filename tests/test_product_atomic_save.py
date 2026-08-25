import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager, ProductDecimalMigration
from repositories import (
    CadastroAuxiliarRepository,
    CategoriaRepository,
    EstoqueRepository,
    ProdutoRepository,
)
from services import EstoqueService, ProdutoService
from services.product_application_service import ProductApplicationService, ProductSaveCommand


SCHEMA = """
CREATE TABLE categorias_produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, ativo INTEGER DEFAULT 1,
 criado_em TEXT, atualizado_em TEXT
);
CREATE TABLE marcas_produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, ativo INTEGER DEFAULT 1,
 criado_em TEXT, atualizado_em TEXT
);
CREATE TABLE fornecedores (
 id INTEGER PRIMARY KEY AUTOINCREMENT, razao_social TEXT, nome_fantasia TEXT NOT NULL UNIQUE,
 cnpj TEXT DEFAULT '', telefone TEXT DEFAULT '', email TEXT DEFAULT '', ativo INTEGER DEFAULT 1,
 criado_em TEXT, atualizado_em TEXT
);
CREATE TABLE unidades_medida (
 id INTEGER PRIMARY KEY AUTOINCREMENT, sigla TEXT NOT NULL UNIQUE, descricao TEXT DEFAULT '',
 permite_fracionado INTEGER DEFAULT 0, ativo INTEGER DEFAULT 1, criado_em TEXT, atualizado_em TEXT
);
CREATE TABLE produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT NOT NULL UNIQUE, nome TEXT NOT NULL,
 preco_venda REAL DEFAULT 0, categoria_id INTEGER, marca_id INTEGER, fornecedor_id INTEGER,
 unidade_id INTEGER, unidade_compra_id INTEGER, fator_conversao REAL DEFAULT 1,
 preco_custo REAL DEFAULT 0, despesas_percentual REAL DEFAULT 0, margem_lucro REAL DEFAULT 0,
 tipo_produto TEXT DEFAULT 'MERCADORIA', controla_estoque INTEGER DEFAULT 1,
 participa_xml INTEGER DEFAULT 1, ativo INTEGER DEFAULT 1, criado_em TEXT, atualizado_em TEXT,
 codigo_barras TEXT NOT NULL DEFAULT '', ncm TEXT NOT NULL DEFAULT '', cest TEXT NOT NULL DEFAULT '',
 cfop TEXT NOT NULL DEFAULT '', estoque_atual REAL NOT NULL DEFAULT 0,
 estoque_minimo REAL NOT NULL DEFAULT 0, permite_estoque_negativo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE historico_precos_produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL, preco_anterior REAL DEFAULT 0,
 preco_novo REAL DEFAULT 0, custo REAL DEFAULT 0, margem_percentual REAL DEFAULT 0, motivo TEXT, data TEXT
);
CREATE TABLE estoque_movimentacoes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL, tipo TEXT NOT NULL,
 quantidade REAL NOT NULL, saldo_anterior REAL NOT NULL, saldo_atual REAL NOT NULL,
 origem TEXT NOT NULL DEFAULT '', origem_id TEXT NOT NULL DEFAULT '', motivo TEXT NOT NULL DEFAULT '',
 usuario TEXT NOT NULL DEFAULT 'Sistema', data TEXT NOT NULL,
 FOREIGN KEY(produto_id) REFERENCES produtos(id)
);
CREATE TABLE auditoria (
 id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, usuario TEXT NOT NULL,
 modulo TEXT NOT NULL, acao TEXT NOT NULL, objeto TEXT NOT NULL DEFAULT '',
 detalhes TEXT NOT NULL DEFAULT '', resultado TEXT NOT NULL
);
"""


class FailingStockService(EstoqueService):
    def ajustar_na_transacao(self, connection, produto_id, novo_saldo, *, motivo, usuario="Sistema"):
        raise RuntimeError("falha simulada no estoque")


class ProductAtomicSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "atomic.db"
        connection = sqlite3.connect(self.path)
        connection.executescript(SCHEMA)
        connection.close()
        self.database = DatabaseManager(self.path)
        ProductDecimalMigration(self.database).run()
        self.product_service = ProdutoService(
            ProdutoRepository(self.database),
            CategoriaRepository(self.database),
            CadastroAuxiliarRepository(self.database),
        )
        self.stock_service = EstoqueService(EstoqueRepository(self.database))
        self.application = ProductApplicationService(self.product_service, self.stock_service)
        self.product_id = self.application.salvar(ProductSaveCommand(
            codigo="P1", nome="Mesa", preco_venda=100, categoria_id=None,
            tipo_produto="MERCADORIA", preco_custo=60, margem_lucro=20,
            estoque_atual=3,
        )).produto_id

    def tearDown(self):
        self.temp.cleanup()

    def test_edit_commits_product_price_history_and_stock_together(self):
        result = self.application.salvar(ProductSaveCommand(
            produto_id=self.product_id, codigo="P1", nome="Mesa Premium",
            preco_venda=150, categoria_id=None, tipo_produto="MERCADORIA",
            preco_custo=80, margem_lucro=25, estoque_atual=7, usuario="Teste",
        ))
        product = self.product_service.buscar(self.product_id)
        history = self.database.fetch_all(
            "SELECT preco_novo FROM historico_precos_produtos WHERE produto_id=? ORDER BY id",
            (self.product_id,),
        )
        movements = self.database.fetch_all(
            "SELECT saldo_anterior,saldo_atual FROM estoque_movimentacoes WHERE produto_id=?",
            (self.product_id,),
        )
        self.assertEqual(product["nome"], "MESA PREMIUM")
        self.assertEqual(product["preco_venda"], 150)
        self.assertEqual(product["estoque_atual"], 7)
        self.assertEqual([row["preco_novo"] for row in history], [100, 150])
        self.assertEqual(len(movements), 1)
        self.assertEqual((movements[0]["saldo_anterior"], movements[0]["saldo_atual"]), (3, 7))
        self.assertTrue(result.estoque_foi_ajustado)

    def test_stock_failure_rolls_back_product_and_price_history(self):
        failing = ProductApplicationService(
            self.product_service,
            FailingStockService(EstoqueRepository(self.database)),
        )
        with self.assertRaisesRegex(RuntimeError, "falha simulada"):
            failing.salvar(ProductSaveCommand(
                produto_id=self.product_id, codigo="P1", nome="Nome que deve reverter",
                preco_venda=999, categoria_id=None, tipo_produto="MERCADORIA",
                preco_custo=500, margem_lucro=30, estoque_atual=8,
            ))
        product = self.product_service.buscar(self.product_id)
        history = self.database.fetch_all(
            "SELECT preco_novo FROM historico_precos_produtos WHERE produto_id=? ORDER BY id",
            (self.product_id,),
        )
        movements = self.database.fetch_all(
            "SELECT id FROM estoque_movimentacoes WHERE produto_id=?",
            (self.product_id,),
        )
        self.assertEqual(product["nome"], "MESA")
        self.assertEqual(product["preco_venda"], 100)
        self.assertEqual(product["estoque_atual"], 3)
        self.assertEqual([row["preco_novo"] for row in history], [100])
        self.assertEqual(movements, [])


if __name__ == "__main__":
    unittest.main()
