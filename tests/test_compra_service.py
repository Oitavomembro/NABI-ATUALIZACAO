import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager, ProductDecimalMigration
from repositories import CompraRepository, EstoqueRepository
from services.compra_service import CompraService


SCHEMA = """
CREATE TABLE fornecedores(id INTEGER PRIMARY KEY, nome_fantasia TEXT, razao_social TEXT, cnpj TEXT DEFAULT '', ativo INTEGER);
CREATE TABLE produtos(
 id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, tipo_produto TEXT, controla_estoque INTEGER,
 ativo INTEGER, estoque_atual REAL DEFAULT 0, estoque_minimo REAL DEFAULT 0,
 permite_estoque_negativo INTEGER DEFAULT 0, preco_custo REAL DEFAULT 0,
 fator_conversao REAL DEFAULT 1, fornecedor_id INTEGER, atualizado_em TEXT
);
CREATE TABLE produto_fornecedores(
 id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, fornecedor_id INTEGER,
 codigo_fornecedor TEXT DEFAULT '', unidade_fornecedor TEXT DEFAULT 'UN', fator_conversao REAL DEFAULT 1,
 ultimo_custo REAL DEFAULT 0, ultima_compra TEXT DEFAULT '', ativo INTEGER DEFAULT 1,
 UNIQUE(produto_id,fornecedor_id,codigo_fornecedor)
);
CREATE TABLE estoque_movimentacoes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, tipo TEXT, quantidade REAL,
 saldo_anterior REAL, saldo_atual REAL, origem TEXT, origem_id TEXT, motivo TEXT, usuario TEXT, data TEXT,
 UNIQUE(origem,origem_id,produto_id)
);
CREATE TABLE pedidos_compra(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fornecedor_id INTEGER, status TEXT, observacao TEXT,
 usuario TEXT, criado_em TEXT, atualizado_em TEXT
);
CREATE TABLE pedido_compra_itens(
 id INTEGER PRIMARY KEY AUTOINCREMENT, pedido_id INTEGER, produto_id INTEGER,
 quantidade_pedida REAL, quantidade_recebida REAL DEFAULT 0, custo_unitario REAL,
 valor_total REAL, observacao TEXT
);
CREATE TABLE recebimentos_compra(
 id INTEGER PRIMARY KEY AUTOINCREMENT, pedido_id INTEGER, documento TEXT, observacao TEXT,
 usuario TEXT, data_recebimento TEXT
);
CREATE TABLE recebimento_compra_itens(
 id INTEGER PRIMARY KEY AUTOINCREMENT, recebimento_id INTEGER, pedido_item_id INTEGER,
 produto_id INTEGER, quantidade REAL, custo_unitario REAL, valor_total REAL
);
CREATE TABLE auditoria(
 id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, usuario TEXT, modulo TEXT, acao TEXT,
 objeto TEXT, detalhes TEXT, resultado TEXT
);
CREATE TABLE assistant_operation_journal(
 id INTEGER PRIMARY KEY AUTOINCREMENT,idempotency_key TEXT NOT NULL UNIQUE,
 operation_kind TEXT NOT NULL,fingerprint TEXT NOT NULL,status TEXT NOT NULL,
 result_json TEXT NOT NULL DEFAULT '',username TEXT NOT NULL,created_at TEXT NOT NULL,
 committed_at TEXT NOT NULL DEFAULT ''
);
"""


class CompraServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "teste.db"
        con = sqlite3.connect(self.db_path)
        con.executescript(SCHEMA)
        con.execute("INSERT INTO fornecedores VALUES(1,'Fornecedor A','Fornecedor A','',1)")
        con.execute("INSERT INTO produtos VALUES(1,'P1','Produto 1','MERCADORIA',1,1,10,0,0,5,1,NULL,'')")
        con.execute("INSERT INTO produtos VALUES(2,'CX1','Caixa 12','MERCADORIA',1,1,0,0,0,0,12,NULL,'')")
        con.execute("INSERT INTO produtos VALUES(3,'S1','Serviço','SERVICO',0,1,0,0,0,0,1,NULL,'')")
        con.commit(); con.close()
        db = DatabaseManager(self.db_path)
        ProductDecimalMigration(db).run()
        self.repo = CompraRepository(db)
        self.estoque = EstoqueRepository(db)
        self.service = CompraService(self.repo, self.estoque)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pedido_agrega_produto_repetido(self):
        pedido = self.service.criar_pedido(1, [
            {'produto_id': 1, 'quantidade': 2, 'custo_unitario': 10},
            {'produto_id': 1, 'quantidade': 3, 'custo_unitario': 12},
        ])
        dados = self.repo.obter_pedido(pedido)
        self.assertEqual(len(dados['itens']), 1)
        self.assertEqual(dados['itens'][0]['quantidade_pedida'], 5)
        self.assertAlmostEqual(dados['itens'][0]['valor_total'], 56)

    def test_recebimento_parcial_e_total(self):
        pedido = self.service.criar_pedido(1, [{'produto_id': 1, 'quantidade': 5, 'custo_unitario': 8}])
        item = self.repo.obter_pedido(pedido)['itens'][0]
        parcial = self.service.receber(pedido, [{'pedido_item_id': item['id'], 'quantidade': 2}])
        self.assertEqual(parcial.status_pedido, 'PARCIAL')
        self.assertEqual(self.estoque.buscar_produto(1)['estoque_atual'], 12)
        final = self.service.receber(pedido, [{'pedido_item_id': item['id'], 'quantidade': 3, 'custo_unitario': 9}])
        self.assertEqual(final.status_pedido, 'RECEBIDO')
        self.assertEqual(self.estoque.buscar_produto(1)['estoque_atual'], 15)
        self.assertEqual(self.repo.buscar_produto(1)['preco_custo'], 9)

    def test_conversao_embalagem_atualiza_estoque_e_custo_unitario(self):
        pedido = self.service.criar_pedido(1, [{'produto_id': 2, 'quantidade': 2, 'custo_unitario': 120}])
        item = self.repo.obter_pedido(pedido)['itens'][0]
        self.service.receber(pedido, [{'pedido_item_id': item['id'], 'quantidade': 2}])
        produto = self.repo.buscar_produto(2)
        self.assertEqual(produto['estoque_atual'], 24)
        self.assertEqual(produto['preco_custo'], 10)

    def test_excesso_reverte_toda_transacao(self):
        pedido = self.service.criar_pedido(1, [{'produto_id': 1, 'quantidade': 2, 'custo_unitario': 8}])
        item = self.repo.obter_pedido(pedido)['itens'][0]
        with self.assertRaises(ValueError):
            self.service.receber(pedido, [{'pedido_item_id': item['id'], 'quantidade': 3}])
        self.assertEqual(self.estoque.buscar_produto(1)['estoque_atual'], 10)
        self.assertEqual(self.repo.obter_pedido(pedido)['status'], 'ABERTO')

    def test_servico_nao_pode_ser_comprado_para_estoque(self):
        with self.assertRaises(ValueError):
            self.service.criar_pedido(1, [{'produto_id': 3, 'quantidade': 1, 'custo_unitario': 10}])

    def test_recebimento_idempotente_retorna_commit_sem_repetir_efeitos(self):
        pedido = self.service.criar_pedido(
            1, [{'produto_id': 1, 'quantidade': 5, 'custo_unitario': 8}]
        )
        item = self.repo.obter_pedido(pedido)['itens'][0]
        kwargs = dict(
            idempotency_key="nabi:purchase:draft-1",
            operation_fingerprint="a" * 64,
        )
        first = self.service.receber(
            pedido, [{'pedido_item_id': item['id'], 'quantidade': 2}], **kwargs
        )
        repeated = self.service.receber(
            pedido, [{'pedido_item_id': item['id'], 'quantidade': 2}], **kwargs
        )
        self.assertEqual(first, repeated)
        self.assertEqual(self.estoque.buscar_produto(1)['estoque_atual'], 12)
        self.assertEqual(
            self.repo.obter_pedido(pedido)['itens'][0]['quantidade_recebida'], 2
        )
        with self.assertRaisesRegex(PermissionError, "outro conteúdo"):
            self.service.receber(
                pedido, [{'pedido_item_id': item['id'], 'quantidade': 1}],
                idempotency_key=kwargs["idempotency_key"],
                operation_fingerprint="b" * 64,
            )

    def test_falha_reverte_diario_idempotente_junto_com_estoque(self):
        pedido = self.service.criar_pedido(
            1, [{'produto_id': 1, 'quantidade': 1, 'custo_unitario': 8}]
        )
        item = self.repo.obter_pedido(pedido)['itens'][0]
        with self.assertRaises(ValueError):
            self.service.receber(
                pedido, [{'pedido_item_id': item['id'], 'quantidade': 2}],
                idempotency_key="nabi:purchase:failed",
                operation_fingerprint="c" * 64,
            )
        row = self.repo.database.fetch_one(
            "SELECT 1 FROM assistant_operation_journal WHERE idempotency_key=?",
            ("nabi:purchase:failed",),
        )
        self.assertIsNone(row)

    def test_criacao_de_pedido_assistida_e_atomica_e_idempotente(self):
        kwargs = {
            "idempotency_key": "nabi:purchase-order:draft-1",
            "operation_fingerprint": "d" * 64,
            "usuario": "operador",
        }
        first = self.service.criar_pedido(
            1, [{"produto_id": 1, "quantidade": "2", "custo_unitario": "8.50"}],
            **kwargs,
        )
        repeated = self.service.criar_pedido(
            1, [{"produto_id": 1, "quantidade": "2", "custo_unitario": "8.50"}],
            **kwargs,
        )
        self.assertEqual(first, repeated)
        self.assertEqual(len(self.repo.listar_pedidos()), 1)
        journal = self.repo.database.fetch_one(
            "SELECT operation_kind,status,username FROM assistant_operation_journal"
        )
        self.assertEqual(tuple(journal), ("PURCHASE_ORDER_CREATE", "COMMITTED", "operador"))
        with self.assertRaisesRegex(PermissionError, "outro conteúdo"):
            self.service.criar_pedido(
                1, [{"produto_id": 1, "quantidade": "1", "custo_unitario": "8.50"}],
                idempotency_key=kwargs["idempotency_key"],
                operation_fingerprint="e" * 64,
            )

    def test_falha_do_pedido_assistido_remove_journal_na_mesma_transacao(self):
        with self.assertRaisesRegex(ValueError, "não controla estoque"):
            self.service.criar_pedido(
                1, [{"produto_id": 3, "quantidade": "1", "custo_unitario": "10"}],
                idempotency_key="nabi:purchase-order:failed",
                operation_fingerprint="f" * 64,
            )
        self.assertIsNone(self.repo.database.fetch_one(
            "SELECT 1 FROM assistant_operation_journal WHERE idempotency_key=?",
            ("nabi:purchase-order:failed",),
        ))


if __name__ == '__main__':
    unittest.main()
