import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager, ProductDecimalMigration, ProductSchemaMigration
from repositories import CadastroAuxiliarRepository, CategoriaRepository, ProdutoRepository
from services import ProdutoService


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
 tipo_produto TEXT DEFAULT 'MERCADORIA',
 controla_estoque INTEGER DEFAULT 1, participa_xml INTEGER DEFAULT 1, ativo INTEGER DEFAULT 1,
 criado_em TEXT, atualizado_em TEXT, codigo_barras TEXT NOT NULL DEFAULT '',
 ncm TEXT NOT NULL DEFAULT '', cest TEXT NOT NULL DEFAULT '', cfop TEXT NOT NULL DEFAULT '',
 estoque_atual REAL NOT NULL DEFAULT 0, estoque_minimo REAL NOT NULL DEFAULT 0,
 permite_estoque_negativo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE historico_precos_produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL, preco_anterior REAL DEFAULT 0,
 preco_novo REAL DEFAULT 0, custo REAL DEFAULT 0, margem_percentual REAL DEFAULT 0, motivo TEXT, data TEXT
);
"""


class ProductLayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "teste.db"
        conn = sqlite3.connect(self.path)
        conn.executescript(SCHEMA)
        conn.close()
        db = DatabaseManager(self.path)
        ProductDecimalMigration(db).run()
        self.service = ProdutoService(ProdutoRepository(db), CategoriaRepository(db), CadastroAuxiliarRepository(db))

    def tearDown(self):
        self.temp.cleanup()

    def test_crud_e_regras_de_servico(self):
        categoria_id = self.service.criar_categoria("Serviços")
        produto_id = self.service.salvar(
            codigo="S001", nome="Montagem", preco_venda=120,
            categoria_id=categoria_id, tipo_produto="SERVIÇO",
        )
        produto = self.service.buscar(produto_id)
        self.assertEqual(produto["tipo_produto"], "SERVICO")
        rows = self.service.listar("Mont", "SERVIÇO")
        self.assertEqual(len(rows), 1)
        self.assertFalse(self.service.alternar_status(produto_id))


    def test_marcas_fornecedores_unidades(self):
        marca_id = self.service.criar_auxiliar("marca", "Nabi")
        fornecedor_id = self.service.criar_auxiliar("fornecedor", "Distribuidora Central", razao_social="Central LTDA")
        unidade_id = self.service.criar_auxiliar("unidade", "cx", descricao="Caixa")
        produto_id = self.service.salvar(
            codigo="P100", nome="Produto Completo", preco_venda=15.5,
            categoria_id=None, tipo_produto="MERCADORIA",
            marca_id=marca_id, fornecedor_id=fornecedor_id, unidade_id=unidade_id,
        )
        produto = self.service.buscar(produto_id)
        self.assertEqual(produto["marca_id"], marca_id)
        self.assertEqual(produto["fornecedor_id"], fornecedor_id)
        self.assertEqual(produto["unidade_id"], unidade_id)
        resultado = self.service.listar("Distribuidora", "TODOS")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["unidade"], "CX")

    def test_formacao_preco_e_historico(self):
        produto_id = self.service.salvar(
            codigo="P200", nome="Produto Precificado", preco_venda=132,
            categoria_id=None, tipo_produto="MERCADORIA",
            preco_custo=100, despesas_percentual=10, margem_lucro=20,
        )
        produto = self.service.buscar(produto_id)
        self.assertEqual(produto["preco_custo"], 100)
        self.assertEqual(produto["despesas_percentual"], 10)
        self.assertEqual(produto["margem_lucro"], 20)
        calculo = self.service.calcular_preco_sugerido(100, 10, 20)
        self.assertEqual(calculo["preco_sugerido"], 132.0)
        total = self.service.produtos.database.fetch_one(
            "SELECT COUNT(*) AS total FROM historico_precos_produtos WHERE produto_id=?", (produto_id,)
        )
        self.assertEqual(total["total"], 1)

    def test_conversao_unidade_compra(self):
        unidade_id = self.service.criar_auxiliar("unidade", "UN", descricao="Unidade")
        caixa_id = self.service.criar_auxiliar("unidade", "CX", descricao="Caixa")
        produto_id = self.service.salvar(
            codigo="P300", nome="Caixa com 12", preco_venda=3,
            categoria_id=None, tipo_produto="MERCADORIA",
            unidade_id=unidade_id, unidade_compra_id=caixa_id, fator_conversao=12,
        )
        produto = self.service.buscar(produto_id)
        self.assertEqual(produto["unidade_compra_id"], caixa_id)
        self.assertEqual(produto["fator_conversao"], 12)
        self.assertEqual(self.service.converter_quantidade_compra(3, 12), 36)
        with self.assertRaises(ValueError):
            self.service.converter_quantidade_compra(1, 0)

    def test_transacao_reverte_em_erro(self):
        db = self.service.produtos.database
        with self.assertRaises(sqlite3.IntegrityError):
            with db.session(write=True) as conn:
                conn.execute("INSERT INTO categorias_produtos(nome) VALUES('Duplicada')")
                conn.execute("INSERT INTO categorias_produtos(nome) VALUES('Duplicada')")
        total = db.fetch_one("SELECT COUNT(*) AS total FROM categorias_produtos WHERE nome='Duplicada'")
        self.assertEqual(total["total"], 0)

    def test_nome_produto_e_salvo_em_caixa_alta(self):
        produto_id = self.service.salvar(
            codigo="PX1", nome="Arroz tipo 1 5kg", preco_venda=10,
            categoria_id=None, tipo_produto="MERCADORIA"
        )
        self.assertEqual(self.service.buscar(produto_id)["nome"], "ARROZ TIPO 1 5KG")

    def test_pesquisa_ignora_acentos_e_inclui_ean_marca_fornecedor(self):
        marca_id = self.service.criar_auxiliar("marca", "São José")
        fornecedor_id = self.service.criar_auxiliar("fornecedor", "Açúcar Brasil")
        self.service.salvar(
            codigo="P400", nome="CAFÉ TORRADO", preco_venda=20, categoria_id=None,
            tipo_produto="MERCADORIA", marca_id=marca_id, fornecedor_id=fornecedor_id,
            codigo_barras="7891234567890",
        )
        self.assertEqual(len(self.service.listar("cafe", "TODOS")), 1)
        self.assertEqual(len(self.service.listar("sao jose", "TODOS")), 1)
        self.assertEqual(len(self.service.listar("acucar", "TODOS")), 1)
        self.assertEqual(len(self.service.listar("7891234567890", "TODOS")), 1)

    def test_similaridade_por_nome_e_ean(self):
        self.service.salvar(
            codigo="P500", nome="ARROZ BRANCO TIPO 1 5KG", preco_venda=30,
            categoria_id=None, tipo_produto="MERCADORIA", codigo_barras="7890000000001",
        )
        similares_nome = self.service.localizar_similares("Arroz branco tipo 1 5 kg")
        self.assertEqual(similares_nome[0]["codigo"], "P500")
        similares_ean = self.service.localizar_similares("Outro produto", codigo_barras="7890000000001")
        self.assertEqual(similares_ean[0]["criterio_similaridade"], "EAN")
        self.assertEqual(similares_ean[0]["similaridade"], 100.0)

    def test_preparar_duplicacao_gera_codigo_unico_e_limpa_dados_sensiveis(self):
        produto_id = self.service.salvar(
            codigo="P600", nome="PRODUTO BASE", preco_venda=10, categoria_id=None,
            tipo_produto="MERCADORIA", codigo_barras="7899999999999", estoque_atual=8,
        )
        duplicado = self.service.preparar_duplicacao(produto_id)
        self.assertEqual(duplicado["codigo"], "P600-COPIA")
        self.assertEqual(duplicado["codigo_barras"], "")
        self.assertEqual(duplicado["estoque_atual"], 0.0)
        self.service.salvar(
            codigo=duplicado["codigo"], nome=duplicado["nome"], preco_venda=duplicado["preco_venda"],
            categoria_id=duplicado["categoria_id"], tipo_produto=duplicado["tipo_produto"],
        )
        outro = self.service.preparar_duplicacao(produto_id)
        self.assertEqual(outro["codigo"], "P600-COPIA-2")

    def test_historico_registra_alteracao_apenas_de_custo(self):
        produto_id = self.service.salvar(
            codigo="P700", nome="PRODUTO CUSTO", preco_venda=50, categoria_id=None,
            tipo_produto="MERCADORIA", preco_custo=20,
        )
        self.service.salvar(
            produto_id=produto_id, codigo="P700", nome="PRODUTO CUSTO", preco_venda=50,
            categoria_id=None, tipo_produto="MERCADORIA", preco_custo=25,
        )
        historico = self.service.listar_historico(produto_id)
        self.assertEqual(len(historico), 2)
        self.assertEqual(historico[0]["custo"], 25)


    def test_remove_indice_unico_legado_de_codigo_barras(self):
        self.service.produtos.database.execute("CREATE UNIQUE INDEX idx_ean_legado_unico ON produtos(codigo_barras)")
        with self.service.produtos.database.session(write=True) as connection:
            ProductSchemaMigration.migrate_connection(connection)
        indices = self.service.produtos.database.fetch_all("PRAGMA index_list(produtos)")
        nomes = {row["name"] for row in indices}
        self.assertNotIn("idx_ean_legado_unico", nomes)
        self.assertIn("idx_produtos_codigo_barras", nomes)
        self.assertIn("idx_produtos_codigo_barras_unico", nomes)
        self.assertIn("idx_produtos_nome_nocase", nomes)
        self.assertIn("idx_produtos_tipo_ativo", nomes)

    def test_codigo_barras_nao_vazio_e_unico_mas_vazio_pode_repetir(self):
        self.service.salvar(
            codigo="EAN1", nome="PRODUTO EAN 1", preco_venda=10,
            categoria_id=None, tipo_produto="MERCADORIA",
            codigo_barras="7891234567890",
        )
        with self.assertRaisesRegex(ValueError, "código de barras"):
            self.service.salvar(
                codigo="EAN2", nome="PRODUTO EAN 2", preco_venda=20,
                categoria_id=None, tipo_produto="MERCADORIA",
                codigo_barras="7891234567890",
            )
        self.service.salvar(
            codigo="SEM1", nome="SEM EAN 1", preco_venda=1,
            categoria_id=None, tipo_produto="MERCADORIA", codigo_barras="",
        )
        self.service.salvar(
            codigo="SEM2", nome="SEM EAN 2", preco_venda=2,
            categoria_id=None, tipo_produto="MERCADORIA", codigo_barras="",
        )

    def test_pesquisa_comum_filtra_no_sql_e_acento_usa_fallback(self):
        self.service.salvar(
            codigo="FAST1", nome="MESA RETANGULAR", preco_venda=100,
            categoria_id=None, tipo_produto="MERCADORIA",
        )
        self.service.salvar(
            codigo="ACC1", nome="CAFÉ ESPECIAL", preco_venda=30,
            categoria_id=None, tipo_produto="MERCADORIA",
        )
        database = self.service.produtos.database
        original = database.fetch_all
        calls = []

        def tracked(sql, parameters=()):
            calls.append((sql, tuple(parameters)))
            return original(sql, parameters)

        database.fetch_all = tracked
        try:
            self.assertEqual(len(self.service.listar("MESA", "TODOS")), 1)
            self.assertEqual(len(calls), 1)
            self.assertIn("LIKE", calls[0][0])
            calls.clear()
            self.assertEqual(len(self.service.listar("cafe", "TODOS")), 1)
            self.assertEqual(len(calls), 2)
        finally:
            database.fetch_all = original

    def test_validacoes(self):
        produto_id = self.service.salvar(codigo="", nome="Teste", preco_venda=1, categoria_id=None, tipo_produto="MERCADORIA")
        self.assertTrue(self.service.buscar(produto_id)["codigo"].isdigit())
        with self.assertRaises(ValueError):
            self.service.salvar(codigo="1", nome="Teste", preco_venda=-1, categoria_id=None, tipo_produto="MERCADORIA")


if __name__ == "__main__":
    unittest.main()
