import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import DatabaseManager
from repositories import NFeImportRepository
from services import NFeDocument, NFeImportService, NFeItem
from services.nfe_xml_service import NFeDuplicata, NFePagamento


SCHEMA = """
CREATE TABLE fornecedores(id INTEGER PRIMARY KEY AUTOINCREMENT,razao_social TEXT,nome_fantasia TEXT,cnpj TEXT,telefone TEXT,email TEXT,ativo INTEGER,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE unidades_medida(id INTEGER PRIMARY KEY AUTOINCREMENT,sigla TEXT,descricao TEXT,permite_fracionado INTEGER,ativo INTEGER,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,codigo TEXT UNIQUE,nome TEXT,preco_venda REAL,preco_custo REAL,despesas_percentual REAL,margem_lucro REAL,preco_venda_decimal TEXT,preco_custo_decimal TEXT,despesas_percentual_decimal TEXT,margem_lucro_decimal TEXT,fator_conversao_decimal TEXT,categoria_id INTEGER,marca_id INTEGER,fornecedor_id INTEGER,unidade_id INTEGER,unidade_compra_id INTEGER,fator_conversao REAL,tipo_produto TEXT,controla_estoque INTEGER,participa_xml INTEGER,codigo_barras TEXT,ncm TEXT,cest TEXT,cfop TEXT,estoque_atual REAL,estoque_minimo REAL,permite_estoque_negativo INTEGER,ativo INTEGER,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE historico_precos_produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,preco_anterior REAL,preco_novo REAL,custo REAL,margem_percentual REAL,preco_anterior_decimal TEXT,preco_novo_decimal TEXT,custo_decimal TEXT,margem_percentual_decimal TEXT,motivo TEXT,data TEXT);
CREATE TABLE produto_fornecedores(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,fornecedor_id INTEGER,codigo_fornecedor TEXT,unidade_fornecedor TEXT,fator_conversao REAL,ultimo_custo REAL,fator_conversao_decimal TEXT,ultimo_custo_decimal TEXT,ultima_compra TEXT,ativo INTEGER,UNIQUE(produto_id,fornecedor_id,codigo_fornecedor));
CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,tipo TEXT,quantidade REAL,saldo_anterior REAL,saldo_atual REAL,origem TEXT,origem_id TEXT,motivo TEXT,usuario TEXT,data TEXT);
CREATE TABLE nfe_importacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,chave TEXT UNIQUE,numero TEXT,fornecedor_cnpj TEXT,fornecedor_nome TEXT,arquivo_origem TEXT,status TEXT,itens_total INTEGER,itens_criados INTEGER,itens_vinculados INTEGER,valor_total TEXT NOT NULL DEFAULT '0',data_importacao TEXT);
CREATE TABLE titulos_financeiros(id INTEGER PRIMARY KEY AUTOINCREMENT,tipo TEXT,origem TEXT,origem_id TEXT,pessoa_id INTEGER,pessoa_nome TEXT,documento TEXT,descricao TEXT,data_emissao TEXT,data_vencimento TEXT,valor_original REAL,valor_pago REAL,status TEXT,observacao TEXT,criado_em TEXT,atualizado_em TEXT);
CREATE TABLE assistant_operation_journal(id INTEGER PRIMARY KEY AUTOINCREMENT,idempotency_key TEXT NOT NULL UNIQUE,operation_kind TEXT NOT NULL,fingerprint TEXT NOT NULL,status TEXT NOT NULL,result_json TEXT NOT NULL DEFAULT '',username TEXT NOT NULL,created_at TEXT NOT NULL,committed_at TEXT NOT NULL DEFAULT '');
"""


class NFeImportAtomicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "db.sqlite"
        conn = sqlite3.connect(self.path)
        conn.executescript(SCHEMA)
        conn.commit(); conn.close()
        self.repo = NFeImportRepository(DatabaseManager(self.path))
        self.service = NFeImportService(
            self.repo,
            actor_provider=lambda: "Operador",
            authorization_provider=lambda _module, _action: True,
        )
        self.doc = NFeDocument(
            chave="CHAVE-ATOMIC", numero="77", fornecedor="Fornecedor", cnpj="123",
            data_emissao="2026-08-02", valor_total=25,
            duplicatas=(NFeDuplicata("001", "2026-09-02", Decimal("25")),),
            pagamentos=(NFePagamento("03", Decimal("25")),),
            itens=(NFeItem("P1", "Produto Um", 2, "UN", 12.5, valor_total=25),),
        )
        self.preparados = [{
            "acao": "CRIAR", "produto_id": None, "quantidade": 2, "fator": 1,
            "unidade": "UN", "custo": 12.5, "margem": 20, "preco": 15,
        }]

    def tearDown(self):
        self.tmp.cleanup()

    def test_importa_produto_estoque_historico_financeiro_na_mesma_transacao(self):
        resultado = self.service.importar_atomicamente(self.doc, arquivo_origem="nfe.xml", itens=self.preparados)
        self.assertEqual(resultado["itens_criados"], 1)
        db = self.repo.database
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM produtos")["n"], 1)
        self.assertEqual(db.fetch_one("SELECT estoque_atual FROM produtos")["estoque_atual"], 2)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM estoque_movimentacoes")["n"], 1)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM historico_precos_produtos")["n"], 1)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM nfe_importacoes")["n"], 1)
        titulo = db.fetch_one("SELECT origem,documento,data_vencimento,valor_original,observacao FROM titulos_financeiros")
        self.assertEqual(titulo["origem"], "NFE_XML")
        self.assertEqual((titulo["documento"], titulo["data_vencimento"]), ("001", "2026-09-02"))
        self.assertEqual(titulo["valor_original"], 25)
        self.assertIn("03", titulo["observacao"])

    def test_sem_duplicatas_nao_inventa_titulo_e_informa_ausencia(self):
        doc = NFeDocument(
            chave="CHAVE-SEM-COBRANCA", numero="79", fornecedor="Fornecedor", cnpj="123",
            data_emissao="2026-08-02", valor_total=25,
            itens=(NFeItem("P1", "Produto Um", 2, "UN", 12.5, valor_total=25),),
        )
        resultado = self.service.importar_atomicamente(doc, arquivo_origem="nfe.xml", itens=self.preparados)
        self.assertEqual(resultado["titulo_ids"], [])
        self.assertFalse(resultado["financeiro_criado"])
        self.assertIn("não informa duplicatas", resultado["financeiro_indicacao"])
        self.assertEqual(self.repo.database.fetch_one("SELECT COUNT(*) n FROM titulos_financeiros")["n"], 0)

    def test_duplicatas_criam_titulos_separados_com_dados_exatos(self):
        doc = NFeDocument(
            chave="CHAVE-PARCELADA", numero="80", fornecedor="Fornecedor", cnpj="123",
            data_emissao="2026-08-02", valor_total=25,
            duplicatas=(
                NFeDuplicata("A", "2026-09-01", Decimal("10.00")),
                NFeDuplicata("B", "2026-10-01", Decimal("15.00")),
            ),
            itens=(NFeItem("P1", "Produto Um", 2, "UN", 12.5, valor_total=25),),
        )
        resultado = self.service.importar_atomicamente(doc, arquivo_origem="nfe.xml", itens=self.preparados)
        self.assertEqual(len(resultado["titulo_ids"]), 2)
        rows = self.repo.database.fetch_all(
            "SELECT documento,data_vencimento,valor_original FROM titulos_financeiros ORDER BY id"
        )
        self.assertEqual(
            [(row["documento"], row["data_vencimento"], row["valor_original"]) for row in rows],
            [("A", "2026-09-01", 10), ("B", "2026-10-01", 15)],
        )

    def test_soma_divergente_reverte_toda_importacao_sem_tolerancia(self):
        self.doc = NFeDocument(
            **{**self.doc.__dict__, "duplicatas": (
                NFeDuplicata("001", "2026-09-02", Decimal("24.999")),
            )}
        )
        with self.assertRaisesRegex(ValueError, "soma exata"):
            self.service.importar_atomicamente(self.doc, arquivo_origem="nfe.xml", itens=self.preparados)
        for table in ("produtos", "estoque_movimentacoes", "titulos_financeiros", "nfe_importacoes"):
            self.assertEqual(self.repo.database.fetch_one(f"SELECT COUNT(*) n FROM {table}")["n"], 0)

    def test_conferencia_pode_corrigir_ncm_cest_e_codigo_de_barras_antes_de_criar(self):
        self.preparados[0].update({
            "codigo_barras": "7891234567890",
            "ncm": "94036000",
            "cest": "2805900",
        })
        self.service.importar_atomicamente(
            self.doc, arquivo_origem="nfe.xml", itens=self.preparados
        )
        product = self.repo.database.fetch_one(
            "SELECT codigo_barras,ncm,cest,cfop FROM produtos"
        )
        self.assertEqual(product["codigo_barras"], "7891234567890")
        self.assertEqual(product["ncm"], "94036000")
        self.assertEqual(product["cest"], "2805900")
        self.assertEqual(product["cfop"], "")

    def test_importa_em_banco_legado_com_descricao_obrigatoria(self):
        connection = sqlite3.connect(self.path)
        connection.execute("DROP TABLE produtos")
        product_schema = next(
            statement for statement in SCHEMA.split(";")
            if statement.strip().startswith("CREATE TABLE produtos(")
        )
        connection.execute(
            product_schema.replace("nome TEXT,", "nome TEXT,descricao TEXT NOT NULL,")
        )
        connection.commit(); connection.close()

        self.service.importar_atomicamente(
            self.doc, arquivo_origem="nfe.xml", itens=self.preparados
        )
        product = self.repo.database.fetch_one("SELECT nome, descricao FROM produtos")
        self.assertEqual(product["nome"], "PRODUTO UM")
        self.assertEqual(product["descricao"], "PRODUTO UM")

    def test_nfe_grava_colunas_decimais_canonicas(self):
        self.preparados[0].update({"preco": "15.123456789", "custo": "12.500000001", "margem": "20.0001", "fator": "1.2500"})
        self.service.importar_atomicamente(self.doc, arquivo_origem="nfe.xml", itens=self.preparados)
        db = self.repo.database
        produto = db.fetch_one("SELECT preco_venda_decimal,preco_custo_decimal,margem_lucro_decimal,fator_conversao_decimal FROM produtos")
        self.assertEqual(produto["preco_venda_decimal"], "15.123456789")
        self.assertEqual(produto["preco_custo_decimal"], "12.500000001")
        self.assertEqual(produto["margem_lucro_decimal"], "20.0001")
        self.assertEqual(produto["fator_conversao_decimal"], "1.25")
        hist = db.fetch_one("SELECT preco_novo_decimal,custo_decimal,margem_percentual_decimal FROM historico_precos_produtos")
        self.assertEqual(hist["preco_novo_decimal"], "15.123456789")
        self.assertEqual(hist["custo_decimal"], "12.500000001")
        vinculo = db.fetch_one("SELECT fator_conversao_decimal,ultimo_custo_decimal FROM produto_fornecedores")
        self.assertEqual(vinculo["fator_conversao_decimal"], "1.25")
        self.assertEqual(vinculo["ultimo_custo_decimal"], "12.500000001")

    def test_nfe_atualiza_coluna_canonica_sem_deixar_valor_antigo(self):
        self.service.importar_atomicamente(self.doc, arquivo_origem="nfe.xml", itens=self.preparados)
        db = self.repo.database
        produto_id = db.fetch_one("SELECT id FROM produtos")["id"]
        segunda = NFeDocument(
            chave="CHAVE-ATOMIC-2", numero="78", fornecedor="Fornecedor", cnpj="123",
            data_emissao="2026-08-03", valor_total=40,
            duplicatas=(NFeDuplicata("001", "2026-09-03", Decimal("40")),),
            itens=(NFeItem("P1", "Produto Um", 1, "UN", 20, valor_total=20),),
        )
        preparados = [{"acao":"ATUALIZAR","produto_id":produto_id,"quantidade":1,"fator":"1","unidade":"UN","custo":"20.000000001","margem":"25.5","preco":"25.000000001"}]
        self.service.importar_atomicamente(segunda, arquivo_origem="nfe2.xml", itens=preparados)
        produto = db.fetch_one("SELECT preco_venda_decimal,preco_custo_decimal,margem_lucro_decimal FROM produtos WHERE id=?", (produto_id,))
        self.assertEqual(produto["preco_venda_decimal"], "25.000000001")
        self.assertEqual(produto["preco_custo_decimal"], "20.000000001")
        self.assertEqual(produto["margem_lucro_decimal"], "25.5")
        hist = db.fetch_one("SELECT preco_anterior_decimal,preco_novo_decimal,custo_decimal FROM historico_precos_produtos WHERE motivo='NFE_XML_ATUALIZAR'")
        self.assertEqual(hist["preco_anterior_decimal"], "15")
        self.assertEqual(hist["preco_novo_decimal"], "25.000000001")
        self.assertEqual(hist["custo_decimal"], "20.000000001")

    def test_revisao_atualiza_cadastro_sem_repetir_estoque_financeiro_ou_nota(self):
        importacao = self.service.importar_atomicamente(
            self.doc, arquivo_origem="nfe.xml", itens=self.preparados
        )
        db = self.repo.database
        produto = db.fetch_one("SELECT id,estoque_atual FROM produtos")
        preparados = [{
            "acao": "ATUALIZAR", "produto_id": produto["id"], "quantidade": 2,
            "fator": 2, "unidade": "UN", "custo": 6.25, "margem": 60,
            "preco": 10, "descricao": "PRODUTO UM REVISADO",
        }]

        resultado = self.service.revisar_produtos_importados(
            importacao["importacao_id"], self.doc, itens=preparados
        )

        self.assertEqual(resultado["produtos_atualizados"], 1)
        revisado = db.fetch_one("SELECT nome,preco_venda,estoque_atual FROM produtos")
        self.assertEqual(revisado["nome"], "PRODUTO UM REVISADO")
        self.assertEqual(revisado["preco_venda"], 10)
        self.assertEqual(revisado["estoque_atual"], produto["estoque_atual"])
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM estoque_movimentacoes")["n"], 1)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM titulos_financeiros")["n"], 1)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM nfe_importacoes")["n"], 1)

    def test_falha_no_financeiro_reverte_toda_importacao(self):
        conn = sqlite3.connect(self.path)
        conn.execute("DROP TABLE titulos_financeiros")
        conn.execute("CREATE TABLE titulos_financeiros(id INTEGER PRIMARY KEY, tipo TEXT NOT NULL, origem TEXT NOT NULL, origem_id TEXT NOT NULL, pessoa_id INTEGER NOT NULL)")
        conn.commit(); conn.close()
        # Tabela incompatível é ignorada por compatibilidade; força falha no último passo via trigger.
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TRIGGER falhar_nfe BEFORE INSERT ON nfe_importacoes BEGIN SELECT RAISE(ABORT, 'falha final'); END")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.importar_atomicamente(self.doc, arquivo_origem="nfe.xml", itens=self.preparados)
        db = self.repo.database
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM produtos")["n"], 0)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM estoque_movimentacoes")["n"], 0)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM historico_precos_produtos")["n"], 0)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM fornecedores")["n"], 0)

    def test_importacao_assistida_e_idempotente_na_mesma_transacao(self):
        fingerprint = "a" * 64
        first = self.service.importar_atomicamente(
            self.doc, arquivo_origem="nfe.xml", itens=self.preparados,
            expected_actor="Operador", idempotency_key="nabi:nfe:teste",
            operation_fingerprint=fingerprint,
        )
        second = self.service.importar_atomicamente(
            self.doc, arquivo_origem="nfe.xml", itens=self.preparados,
            expected_actor="Operador", idempotency_key="nabi:nfe:teste",
            operation_fingerprint=fingerprint,
        )
        self.assertEqual(second, first)
        db = self.repo.database
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM nfe_importacoes")["n"], 1)
        self.assertEqual(db.fetch_one("SELECT COUNT(*) n FROM estoque_movimentacoes")["n"], 1)
        journal = db.fetch_one("SELECT status,username FROM assistant_operation_journal")
        self.assertEqual((journal["status"], journal["username"]), ("COMMITTED", "Operador"))

    def test_idempotencia_rejeita_mesma_chave_com_outro_conteudo(self):
        self.service.importar_atomicamente(
            self.doc, arquivo_origem="nfe.xml", itens=self.preparados,
            idempotency_key="nabi:nfe:teste", operation_fingerprint="a" * 64,
        )
        with self.assertRaisesRegex(ValueError, "outra operação"):
            self.service.importar_atomicamente(
                self.doc, arquivo_origem="nfe.xml", itens=self.preparados,
                idempotency_key="nabi:nfe:teste", operation_fingerprint="b" * 64,
            )

    def test_falha_assistida_reverte_diario_estoque_financeiro_e_nota(self):
        conn = sqlite3.connect(self.path)
        conn.execute(
            "CREATE TRIGGER falhar_nfe_assistida BEFORE INSERT ON nfe_importacoes "
            "BEGIN SELECT RAISE(ABORT, 'falha final'); END"
        )
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.importar_atomicamente(
                self.doc, arquivo_origem="nfe.xml", itens=self.preparados,
                idempotency_key="nabi:nfe:rollback", operation_fingerprint="c" * 64,
            )
        db = self.repo.database
        for table in (
            "assistant_operation_journal", "produtos", "estoque_movimentacoes",
            "titulos_financeiros", "nfe_importacoes",
        ):
            self.assertEqual(db.fetch_one(f"SELECT COUNT(*) n FROM {table}")["n"], 0)

    def test_importacao_sem_sessao_falha_antes_de_gravar(self):
        service = NFeImportService(self.repo)
        with self.assertRaisesRegex(PermissionError, "sessão autenticada"):
            service.importar_atomicamente(
                self.doc, arquivo_origem="nfe.xml", itens=self.preparados
            )
        self.assertEqual(
            self.repo.database.fetch_one("SELECT COUNT(*) n FROM nfe_importacoes")["n"],
            0,
        )

    def test_importacao_exige_permissoes_reais_antes_de_gravar(self):
        checked = []
        service = NFeImportService(
            self.repo,
            actor_provider=lambda: "Operador",
            authorization_provider=lambda module, action: (
                checked.append((module, action)) or (module, action) != ("produtos", "create")
            ),
        )
        with self.assertRaisesRegex(PermissionError, "produtos/create"):
            service.importar_atomicamente(
                self.doc, arquivo_origem="nfe.xml", itens=self.preparados
            )
        self.assertIn(("compras", "receive"), checked)
        self.assertIn(("financeiro", "create"), checked)
        self.assertIn(("produtos", "create"), checked)
        self.assertEqual(
            self.repo.database.fetch_one("SELECT COUNT(*) n FROM nfe_importacoes")["n"],
            0,
        )

    def test_confirmacao_nabi_de_outra_sessao_falha_antes_de_gravar(self):
        with self.assertRaisesRegex(PermissionError, "outra sessão"):
            self.service.importar_atomicamente(
                self.doc, arquivo_origem="nfe.xml", itens=self.preparados,
                expected_actor="OutroOperador",
            )
        self.assertEqual(
            self.repo.database.fetch_one("SELECT COUNT(*) n FROM nfe_importacoes")["n"],
            0,
        )

    def test_estorno_e_revisao_nao_aceitam_usuario_livre(self):
        with self.assertRaisesRegex(TypeError, "usuario"):
            self.service.estornar_importacao(1, usuario="forjado")
        with self.assertRaisesRegex(TypeError, "usuario"):
            self.service.revisar_produtos_importados(
                1, self.doc, itens=self.preparados, usuario="forjado"
            )

    def test_estorno_sem_sessao_preserva_importacao_e_estoque(self):
        imported = self.service.importar_atomicamente(
            self.doc, arquivo_origem="nfe.xml", itens=self.preparados
        )
        before = self.repo.database.fetch_one(
            "SELECT estoque_atual FROM produtos"
        )["estoque_atual"]
        untrusted = NFeImportService(self.repo)
        with self.assertRaisesRegex(PermissionError, "sessão autenticada"):
            untrusted.estornar_importacao(imported["importacao_id"])
        self.assertEqual(
            self.repo.database.fetch_one(
                "SELECT status FROM nfe_importacoes WHERE id=?",
                (imported["importacao_id"],),
            )["status"],
            "CONCLUIDA",
        )
        self.assertEqual(
            self.repo.database.fetch_one("SELECT estoque_atual FROM produtos")["estoque_atual"],
            before,
        )

    def test_exclusao_tecnica_exige_permissao_exclusiva(self):
        imported = self.service.importar_atomicamente(
            self.doc, arquivo_origem="nfe.xml", itens=self.preparados
        )
        service = NFeImportService(
            self.repo,
            actor_provider=lambda: "Gerente",
            authorization_provider=lambda module, action: (
                module, action
            ) != ("technical", "delete"),
        )
        with self.assertRaisesRegex(PermissionError, "technical/delete"):
            service.excluir_importacao(imported["importacao_id"])
        self.assertIsNotNone(
            self.repo.database.fetch_one(
                "SELECT id FROM nfe_importacoes WHERE id=?",
                (imported["importacao_id"],),
            )
        )


if __name__ == "__main__":
    unittest.main()
