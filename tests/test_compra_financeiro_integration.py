import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager, ProductDecimalMigration
from repositories import CompraRepository, EstoqueRepository, FinanceiroRepository
from services import CompraService, FinanceiroService


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE fornecedores(id INTEGER PRIMARY KEY,nome_fantasia TEXT,razao_social TEXT,cnpj TEXT,ativo INTEGER);
CREATE TABLE produtos(id INTEGER PRIMARY KEY,codigo TEXT,nome TEXT,tipo_produto TEXT,controla_estoque INTEGER,ativo INTEGER,estoque_atual REAL,preco_custo REAL,fator_conversao REAL,fornecedor_id INTEGER,atualizado_em TEXT);
CREATE TABLE pedidos_compra(id INTEGER PRIMARY KEY AUTOINCREMENT,fornecedor_id INTEGER,status TEXT,observacao TEXT,usuario TEXT,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE pedido_compra_itens(id INTEGER PRIMARY KEY AUTOINCREMENT,pedido_id INTEGER,produto_id INTEGER,quantidade_pedida REAL,quantidade_recebida REAL,custo_unitario REAL,valor_total REAL,observacao TEXT);
CREATE TABLE recebimentos_compra(id INTEGER PRIMARY KEY AUTOINCREMENT,pedido_id INTEGER,documento TEXT,observacao TEXT,usuario TEXT,data_recebimento TEXT);
CREATE TABLE recebimento_compra_itens(id INTEGER PRIMARY KEY AUTOINCREMENT,recebimento_id INTEGER,pedido_item_id INTEGER,produto_id INTEGER,quantidade REAL,custo_unitario REAL,valor_total REAL);
CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,tipo TEXT,quantidade REAL,saldo_anterior REAL,saldo_atual REAL,origem TEXT,origem_id TEXT,motivo TEXT,usuario TEXT,data TEXT);
CREATE UNIQUE INDEX idx_estoque_movimentacoes_origem ON estoque_movimentacoes(origem,origem_id) WHERE origem_id<>'';
CREATE TABLE produto_fornecedores(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,fornecedor_id INTEGER,codigo_fornecedor TEXT,unidade_fornecedor TEXT,fator_conversao REAL,ultimo_custo REAL,ultima_compra TEXT,ativo INTEGER, UNIQUE(produto_id,fornecedor_id,codigo_fornecedor));
CREATE TABLE auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,usuario TEXT,modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
CREATE TABLE titulos_financeiros(id INTEGER PRIMARY KEY AUTOINCREMENT,tipo TEXT,origem TEXT,origem_id TEXT,pessoa_id INTEGER,pessoa_nome TEXT,documento TEXT,descricao TEXT,data_emissao TEXT,data_vencimento TEXT,valor_original REAL,valor_pago REAL,status TEXT,observacao TEXT,criado_em TEXT,atualizado_em TEXT);
CREATE UNIQUE INDEX idx_titulos_origem_unica ON titulos_financeiros(tipo,origem,origem_id,documento) WHERE origem_id<>'' AND status<>'CANCELADO';
CREATE TABLE pagamentos_titulos(id INTEGER PRIMARY KEY AUTOINCREMENT,titulo_id INTEGER,valor REAL,forma_pagamento TEXT,observacao TEXT,usuario TEXT,data_pagamento TEXT);
"""


class CompraFinanceiroIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = str(Path(self.tmp.name) / "db.sqlite")
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO fornecedores VALUES(1,'Fornecedor A','Fornecedor A','123',1)")
        conn.execute("INSERT INTO produtos VALUES(1,'P1','Produto','MERCADORIA',1,1,0,0,1,NULL,'')")
        conn.commit(); conn.close()
        db=DatabaseManager(path)
        ProductDecimalMigration(db).run()
        fin=FinanceiroService(FinanceiroRepository(db))
        self.compra=CompraService(CompraRepository(db), EstoqueRepository(db), fin)
        self.fin_repo=fin.repository

    def tearDown(self): self.tmp.cleanup()

    def test_recebimento_gera_conta_pagar_na_mesma_transacao(self):
        pedido=self.compra.criar_pedido(1,[{"produto_id":1,"quantidade":2,"custo_unitario":10}])
        item=self.compra.repository.obter_pedido(pedido)["itens"][0]
        resultado=self.compra.receber(
            pedido,[{"pedido_item_id":item["id"],"quantidade":2,"custo_unitario":10}],
            documento="NF-1",gerar_conta_pagar=True,data_vencimento="2026-08-30"
        )
        titulos=self.fin_repo.listar_titulos(tipo="PAGAR")
        self.assertEqual(resultado.valor_total,20.0)
        self.assertEqual(len(titulos),1)
        self.assertEqual(titulos[0]["valor_original"],20.0)
        self.assertEqual(titulos[0]["origem"],"RECEBIMENTO_COMPRA")

    def test_erro_financeiro_reverte_estoque_e_recebimento(self):
        pedido=self.compra.criar_pedido(1,[{"produto_id":1,"quantidade":1,"custo_unitario":10}])
        item=self.compra.repository.obter_pedido(pedido)["itens"][0]
        with self.assertRaisesRegex(ValueError,"vencimento"):
            self.compra.receber(
                pedido,[{"pedido_item_id":item["id"],"quantidade":1}],gerar_conta_pagar=True
            )
        produto=self.compra.repository.buscar_produto(1)
        self.assertEqual(produto["estoque_atual"],0)
        self.assertEqual(self.compra.repository.obter_pedido(pedido)["itens"][0]["quantidade_recebida"],0)


if __name__ == '__main__': unittest.main()
