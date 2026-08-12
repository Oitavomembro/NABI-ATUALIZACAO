from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from repositories import NFeImportRepository


SCHEMA = """
CREATE TABLE produtos (id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, estoque_atual REAL, atualizado_em TEXT);
CREATE TABLE estoque_movimentacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, tipo TEXT, quantidade REAL, saldo_anterior REAL, saldo_atual REAL, origem TEXT, origem_id TEXT, motivo TEXT, usuario TEXT, data TEXT);
CREATE TABLE nfe_importacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE, numero TEXT, fornecedor_cnpj TEXT, fornecedor_nome TEXT, arquivo_origem TEXT, status TEXT, itens_total INTEGER, itens_criados INTEGER, itens_vinculados INTEGER, data_importacao TEXT);
CREATE TABLE nfe_documentos_origem (id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT, numero TEXT);
CREATE TABLE nfe_documentos_origem_itens (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_id INTEGER);
CREATE TABLE nfe_devolucoes (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_origem_id INTEGER);
CREATE TABLE titulos_financeiros (id INTEGER PRIMARY KEY AUTOINCREMENT, origem TEXT, origem_id TEXT, valor_pago REAL);
"""


class NFeImportDeleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "teste.db"
        con = sqlite3.connect(self.db_path)
        con.executescript(SCHEMA)
        con.execute("INSERT INTO produtos(id,codigo,nome,estoque_atual,atualizado_em) VALUES(1,'P1','Produto 1',15,'')")
        con.execute("INSERT INTO nfe_importacoes(id,chave,numero,fornecedor_nome,status,itens_total,itens_criados,itens_vinculados,data_importacao) VALUES(1,?,?,?,'CONCLUIDA',1,1,0,'2026-08-02 10:00:00')", ('1'*44,'123','Fornecedor'))
        con.execute("INSERT INTO nfe_documentos_origem(id,chave,numero) VALUES(1,?,?)", ('1'*44,'123'))
        con.execute("INSERT INTO nfe_documentos_origem_itens(documento_id) VALUES(1)")
        con.execute("INSERT INTO estoque_movimentacoes(produto_id,tipo,quantidade,saldo_anterior,saldo_atual,origem,origem_id,motivo,usuario,data) VALUES(1,'ENTRADA',10,5,15,'NFE_XML',?,'','','2026-08-02 10:00:00')", ('1'*44+':0',))
        con.commit(); con.close()
        self.repo = NFeImportRepository(DatabaseManager(self.db_path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_lista_por_periodo(self):
        notas = self.repo.listar_importacoes('2026-08-01','2026-08-03')
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]['numero'], '123')

    def test_analisa_e_exclui_revertendo_estoque(self):
        impacto = self.repo.analisar_exclusao(1)
        self.assertTrue(impacto['pode_excluir'])
        self.assertEqual(impacto['movimentos'][0]['estoque_apos_reversao'], 5)
        resultado = self.repo.excluir_importacao(1)
        self.assertEqual(resultado['movimentos_revertidos'], 1)
        con = sqlite3.connect(self.db_path)
        estoque = con.execute('SELECT estoque_atual FROM produtos WHERE id=1').fetchone()[0]
        self.assertEqual(estoque, 5)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM nfe_importacoes').fetchone()[0], 0)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM estoque_movimentacoes').fetchone()[0], 0)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM nfe_documentos_origem').fetchone()[0], 0)
        con.close()

    def test_reverte_multiplas_linhas_do_mesmo_produto_cumulativamente(self):
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT INTO estoque_movimentacoes(produto_id,tipo,quantidade,saldo_anterior,saldo_atual,origem,origem_id,motivo,usuario,data) VALUES(1,'ENTRADA',2,15,17,'NFE_XML',?,'','','2026-08-02 10:01:00')", ('1'*44+':1',))
        con.execute('UPDATE produtos SET estoque_atual=17 WHERE id=1')
        con.commit(); con.close()
        impacto = self.repo.analisar_exclusao(1)
        self.assertEqual(len(impacto['movimentos']), 1)
        self.assertEqual(impacto['movimentos'][0]['quantidade_reverter'], 12)
        self.repo.excluir_importacao(1)
        con = sqlite3.connect(self.db_path)
        self.assertEqual(con.execute('SELECT estoque_atual FROM produtos WHERE id=1').fetchone()[0], 5)
        con.close()

    def test_bloqueia_se_estoque_ja_foi_consumido(self):
        con = sqlite3.connect(self.db_path)
        con.execute('UPDATE produtos SET estoque_atual=3 WHERE id=1')
        con.commit(); con.close()
        impacto = self.repo.analisar_exclusao(1)
        self.assertFalse(impacto['pode_excluir'])
        with self.assertRaises(ValueError):
            self.repo.excluir_importacao(1)

    def test_bloqueia_nota_com_devolucao(self):
        con = sqlite3.connect(self.db_path)
        con.execute('INSERT INTO nfe_devolucoes(documento_origem_id) VALUES(1)')
        con.commit(); con.close()
        impacto = self.repo.analisar_exclusao(1)
        self.assertFalse(impacto['pode_excluir'])


if __name__ == '__main__':
    unittest.main()
