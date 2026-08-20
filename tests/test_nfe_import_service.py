import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager, ProductDecimalMigration
from repositories import NFeImportRepository
from services import NFeDocument, NFeImportService, NFeItem


class NFeImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "nfe.db"
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE fornecedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                razao_social TEXT NOT NULL DEFAULT '',
                nome_fantasia TEXT NOT NULL,
                cnpj TEXT NOT NULL DEFAULT '',
                telefone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT '',
                atualizado_em TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE unidades_medida (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sigla TEXT NOT NULL,
                descricao TEXT NOT NULL DEFAULT '',
                permite_fracionado INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT '',
                atualizado_em TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL,
                nome TEXT NOT NULL,
                codigo_barras TEXT NOT NULL DEFAULT '',
                ncm TEXT NOT NULL DEFAULT '',
                cest TEXT NOT NULL DEFAULT '',
                cfop TEXT NOT NULL DEFAULT '',
                fiscal_origin TEXT NOT NULL DEFAULT '',
                fiscal_profile_source TEXT NOT NULL DEFAULT '',
                ibs_cbs_cst TEXT NOT NULL DEFAULT '',
                ibs_cbs_class TEXT NOT NULL DEFAULT '',
                ibs_uf_rate TEXT NOT NULL DEFAULT '0',
                ibs_city_rate TEXT NOT NULL DEFAULT '0',
                cbs_rate TEXT NOT NULL DEFAULT '0',
                fornecedor_id INTEGER,
                unidade_compra_id INTEGER,
                preco_venda REAL NOT NULL DEFAULT 0,
                preco_custo REAL NOT NULL DEFAULT 0,
                despesas_percentual REAL NOT NULL DEFAULT 0,
                margem_lucro REAL NOT NULL DEFAULT 0,
                fator_conversao REAL NOT NULL DEFAULT 1,
                atualizado_em TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE produto_fornecedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                fornecedor_id INTEGER NOT NULL,
                codigo_fornecedor TEXT NOT NULL DEFAULT '',
                unidade_fornecedor TEXT NOT NULL DEFAULT 'UN',
                fator_conversao REAL NOT NULL DEFAULT 1,
                ultimo_custo REAL NOT NULL DEFAULT 0,
                ultima_compra TEXT NOT NULL DEFAULT '',
                ativo INTEGER NOT NULL DEFAULT 1,
                UNIQUE(produto_id, fornecedor_id, codigo_fornecedor)
            );
            CREATE TABLE nfe_importacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL UNIQUE,
                numero TEXT NOT NULL DEFAULT '',
                fornecedor_cnpj TEXT NOT NULL DEFAULT '',
                fornecedor_nome TEXT NOT NULL DEFAULT '',
                arquivo_origem TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'CONCLUIDA',
                itens_total INTEGER NOT NULL DEFAULT 0,
                itens_criados INTEGER NOT NULL DEFAULT 0,
                itens_vinculados INTEGER NOT NULL DEFAULT 0,
                valor_total TEXT NOT NULL DEFAULT '0',
                data_importacao TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()
        db = DatabaseManager(self.db_path)
        ProductDecimalMigration(db).run()
        self.repo = NFeImportRepository(db)
        self.service = NFeImportService(self.repo)
        self.doc = NFeDocument(
            chave="35123456789012345678901234567890123456789012",
            numero="123",
            fornecedor="Fornecedor Teste",
            cnpj="12345678000199",
            itens=(NFeItem("ABC", "Produto A", 2, "UN", 10, codigo_barras="7891"),),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_analisa_item_novo_e_produto_por_ean(self):
        analise = self.service.analisar(self.doc)[0]
        self.assertEqual(analise.status, "NOVO")
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO produtos(codigo,nome,codigo_barras) VALUES('OUTRO','Produto A','7891')")
        conn.commit(); conn.close()
        analise = self.service.analisar(self.doc)[0]
        self.assertEqual(analise.status, "VINCULAR")
        self.assertEqual(analise.criterio, "EAN")

    def test_registra_e_bloqueia_importacao_duplicada(self):
        self.service.registrar_resultado(self.doc, arquivo_origem="nota.xml", itens_criados=1, itens_vinculados=0)
        with self.assertRaises(ValueError):
            self.service.validar_nao_importada(self.doc)

    def test_localiza_fornecedor_por_cnpj_formatado(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO fornecedores(nome_fantasia,cnpj) VALUES('Fornecedor Teste','12.345.678/0001-99')")
        conn.commit(); conn.close()
        fornecedor = self.service.fornecedor_existente(self.doc)
        self.assertIsNotNone(fornecedor)
        self.assertEqual(fornecedor["nome_fantasia"], "Fornecedor Teste")

    def test_vinculo_fornecedor_e_atualizacao_de_custo(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO fornecedores(nome_fantasia,cnpj) VALUES('Fornecedor Teste','12345678000199')")
        fornecedor_id = conn.execute("SELECT id FROM fornecedores").fetchone()[0]
        conn.execute("INSERT INTO produtos(codigo,nome) VALUES('ABC','Produto A')")
        produto_id = conn.execute("SELECT id FROM produtos").fetchone()[0]
        conn.commit(); conn.close()
        self.repo.atualizar_produto_por_xml(
            produto_id,
            fornecedor_id=fornecedor_id,
            unidade_compra_id=None,
            preco_custo=12.5,
            codigo_barras="7891",
            ncm="12345678",
            cest="",
            cfop="5102",
        )
        self.repo.vincular_produto_fornecedor(
            produto_id=produto_id,
            fornecedor_id=fornecedor_id,
            codigo_fornecedor="ABC",
            unidade_fornecedor="UN",
            fator_conversao=1,
            ultimo_custo=12.5,
        )
        row = self.repo.database.fetch_one("SELECT preco_custo,codigo_barras,ncm,cfop FROM produtos WHERE id=?", (produto_id,))
        self.assertEqual(row["preco_custo"], 12.5)
        self.assertEqual(row["codigo_barras"], "7891")
        self.assertEqual(row["cfop"], "")
        vinculo = self.repo.database.fetch_one("SELECT ultimo_custo FROM produto_fornecedores WHERE produto_id=?", (produto_id,))
        self.assertEqual(vinculo["ultimo_custo"], 12.5)

    def test_analisar_retorna_similaridade_e_candidatos(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO produtos(codigo,nome,codigo_barras) VALUES('ZZZ','PRODUTO A PREMIUM','')")
        conn.commit(); conn.close()
        doc = NFeDocument(
            chave=self.doc.chave, numero=self.doc.numero, fornecedor=self.doc.fornecedor,
            cnpj=self.doc.cnpj, itens=(NFeItem('OUTRO', 'Produto A Premium 1L', 1, 'UN', 10),),
        )
        analise = self.service.analisar(doc)[0]
        self.assertEqual(analise.status, 'REVISAR')
        self.assertGreaterEqual(analise.similaridade, 45)
        self.assertTrue(analise.candidatos)
        self.assertEqual(analise.produto_id, analise.candidatos[0].produto_id)

    def test_preserva_ficha_ibs_cbs_recebida_no_xml(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO produtos(codigo,nome) VALUES('RTC','Produto RTC')")
        produto_id = conn.execute("SELECT id FROM produtos WHERE codigo='RTC'").fetchone()[0]
        item = NFeItem(
            "RTC", "Produto RTC", 1, "UN", 10,
            origem_mercadoria="1",
            ibs_cbs_cst="000", ibs_cbs_class="000001",
            ibs_uf_rate=0.1, ibs_city_rate=0, cbs_rate=0.9,
        )
        self.repo._salvar_tributacao_rtc(conn, produto_id=produto_id, item=item)
        row = conn.execute(
            "SELECT fiscal_origin,fiscal_profile_source,ibs_cbs_cst,ibs_cbs_class,ibs_uf_rate,ibs_city_rate,cbs_rate FROM produtos WHERE id=?",
            (produto_id,),
        ).fetchone()
        conn.close()
        self.assertEqual(row, ("1", "XML_IMPORT", "000", "000001", "0.1", "0", "0.9"))

    def test_validar_decisao_exige_vinculo_coerente(self):
        self.service.validar_decisao('CRIAR', None)
        self.service.validar_decisao('ATUALIZAR', 1)
        with self.assertRaises(ValueError):
            self.service.validar_decisao('VINCULAR', None)
        with self.assertRaises(ValueError):
            self.service.validar_decisao('CRIAR', 1)


if __name__ == "__main__":
    unittest.main()
