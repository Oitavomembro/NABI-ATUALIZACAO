from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager, ProductDecimalMigration
from repositories import CategoriaRepository, ClienteRepository, ProdutoRepository
from services.customer_registration_service import CustomerRegistrationService
from services.produto_service import ProdutoService


PRODUCT_SCHEMA = """
CREATE TABLE categorias_produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, ativo INTEGER DEFAULT 1,
 criado_em TEXT, atualizado_em TEXT
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
 id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL,
 preco_anterior REAL DEFAULT 0, preco_novo REAL DEFAULT 0, custo REAL DEFAULT 0,
 margem_percentual REAL DEFAULT 0, motivo TEXT, data TEXT
);
"""


class FailingHistoryProdutoRepository(ProdutoRepository):
    def registrar_historico_preco(self, *args, **kwargs):
        raise RuntimeError("falha simulada no histórico")


class CadastroTransactionIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "cadastros.db"
        connection = sqlite3.connect(self.path)
        connection.executescript(
            """
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE,
                numero_ficha INTEGER UNIQUE, nome TEXT NOT NULL, cpf TEXT, rg TEXT,
                telefone TEXT, endereco TEXT, observacoes TEXT, limite REAL,
                saldo_devedor REAL
            );
            """ + PRODUCT_SCHEMA
        )
        connection.close()
        self.database = DatabaseManager(self.path)
        ProductDecimalMigration(self.database).run()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_cliente_reverte_insercao_quando_transacao_falha(self) -> None:
        repository = ClienteRepository(self.database)
        service = CustomerRegistrationService(
            repository,
            get_config=lambda _key: "5500",
            set_config=lambda _key, _value: None,
        )
        original_create = repository.criar

        def create_then_fail(data, connection=None):
            original_create(data, connection=connection)
            raise RuntimeError("falha simulada")

        repository.criar = create_then_fail  # type: ignore[method-assign]
        with self.assertRaisesRegex(RuntimeError, "falha simulada"):
            service.criar(nome="Cliente rollback", numero_ficha=5500)

        self.assertEqual(self.database.fetch_one("SELECT COUNT(*) AS total FROM clientes")["total"], 0)

    def test_produto_reverte_gravacao_quando_historico_falha(self) -> None:
        repository = FailingHistoryProdutoRepository(self.database)
        service = ProdutoService(repository, CategoriaRepository(self.database))

        with self.assertRaisesRegex(RuntimeError, "falha simulada no histórico"):
            service.salvar(
                codigo="P-ROLLBACK",
                nome="Produto rollback",
                preco_venda=10,
                categoria_id=None,
                tipo_produto="MERCADORIA",
                preco_custo=5,
                margem_lucro=20,
            )

        self.assertEqual(self.database.fetch_one("SELECT COUNT(*) AS total FROM produtos")["total"], 0)

    def test_produto_reutiliza_transacao_fornecida_sem_abrir_outra(self) -> None:
        repository = ProdutoRepository(self.database)
        service = ProdutoService(repository, CategoriaRepository(self.database))

        def unexpected_transaction():
            raise AssertionError("não deve abrir transação aninhada")

        repository.transaction = unexpected_transaction  # type: ignore[method-assign]
        with self.database.session(write=True) as connection:
            produto_id = service.salvar(
                codigo="P-EXTERNA", nome="Produto transação externa", preco_venda=12,
                categoria_id=None, tipo_produto="MERCADORIA", connection=connection,
            )
            self.assertGreater(produto_id, 0)

        self.assertEqual(
            self.database.fetch_one("SELECT COUNT(*) AS total FROM produtos")["total"], 1
        )


if __name__ == "__main__":
    unittest.main()
