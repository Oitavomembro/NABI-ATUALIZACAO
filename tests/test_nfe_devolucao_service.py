import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from database import DatabaseManager
from repositories import NFeDevolucaoRepository
from services import FiscalService, NFeDevolucaoService, NFeDocument, NFeItem


SCHEMA = """
CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT NOT NULL DEFAULT '');
CREATE TABLE nfe_documentos_origem (
 id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT NOT NULL DEFAULT '', numero TEXT NOT NULL DEFAULT '',
 emitente_nome TEXT NOT NULL DEFAULT '', emitente_documento TEXT NOT NULL DEFAULT '',
 destinatario_nome TEXT NOT NULL DEFAULT '', destinatario_documento TEXT NOT NULL DEFAULT '',
 data_emissao TEXT NOT NULL DEFAULT '', serie TEXT NOT NULL DEFAULT '', modelo TEXT NOT NULL DEFAULT '',
 valor_total REAL NOT NULL DEFAULT 0, arquivo_origem TEXT NOT NULL DEFAULT '',
 criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_nfe_documentos_origem_chave ON nfe_documentos_origem(chave) WHERE chave<>'';
CREATE TABLE nfe_documentos_origem_itens (
 id INTEGER PRIMARY KEY AUTOINCREMENT, documento_id INTEGER NOT NULL, item_numero INTEGER NOT NULL,
 codigo TEXT NOT NULL DEFAULT '', descricao TEXT NOT NULL DEFAULT '', quantidade REAL NOT NULL DEFAULT 0,
 unidade TEXT NOT NULL DEFAULT 'UN', valor_unitario REAL NOT NULL DEFAULT 0, valor_total REAL NOT NULL DEFAULT 0,
 ncm TEXT NOT NULL DEFAULT '', cfop TEXT NOT NULL DEFAULT '', cest TEXT NOT NULL DEFAULT '', codigo_barras TEXT NOT NULL DEFAULT '',
 origem_mercadoria TEXT NOT NULL DEFAULT '', cst_icms TEXT NOT NULL DEFAULT '', csosn TEXT NOT NULL DEFAULT '',
 cst_pis TEXT NOT NULL DEFAULT '', cst_cofins TEXT NOT NULL DEFAULT '',
 FOREIGN KEY(documento_id) REFERENCES nfe_documentos_origem(id) ON DELETE CASCADE
);
CREATE TABLE nfe_devolucoes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, documento_origem_id INTEGER NOT NULL,
 tipo TEXT NOT NULL CHECK(tipo IN ('INTEGRAL','PARCIAL')), motivo TEXT NOT NULL DEFAULT '',
 observacoes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'RASCUNHO', valor_total REAL NOT NULL DEFAULT 0,
 numero_devolucao TEXT NOT NULL DEFAULT '', xml_rascunho TEXT NOT NULL DEFAULT '',
 hash_xml TEXT NOT NULL DEFAULT '', finalizado_em TEXT NOT NULL DEFAULT '',
 criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL,
 FOREIGN KEY(documento_origem_id) REFERENCES nfe_documentos_origem(id)
);
CREATE TABLE nfe_devolucao_itens (
 id INTEGER PRIMARY KEY AUTOINCREMENT, devolucao_id INTEGER NOT NULL, item_origem_id INTEGER NOT NULL,
 quantidade REAL NOT NULL, valor_unitario REAL NOT NULL DEFAULT 0, valor_total REAL NOT NULL DEFAULT 0,
 FOREIGN KEY(devolucao_id) REFERENCES nfe_devolucoes(id) ON DELETE CASCADE,
 FOREIGN KEY(item_origem_id) REFERENCES nfe_documentos_origem_itens(id)
);
CREATE TABLE produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT NOT NULL, codigo_barras TEXT NOT NULL DEFAULT '',
 nome TEXT NOT NULL, estoque_atual REAL NOT NULL DEFAULT 0, controla_estoque INTEGER NOT NULL DEFAULT 1,
 permite_estoque_negativo INTEGER NOT NULL DEFAULT 0, atualizado_em TEXT NOT NULL DEFAULT ''
);
CREATE TABLE estoque_movimentacoes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL, tipo TEXT NOT NULL, quantidade REAL NOT NULL,
 saldo_anterior REAL NOT NULL, saldo_atual REAL NOT NULL, origem TEXT NOT NULL, origem_id TEXT NOT NULL DEFAULT '',
 motivo TEXT NOT NULL DEFAULT '', usuario TEXT NOT NULL DEFAULT '', data TEXT NOT NULL
);
"""


class NFeDevolucaoServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "teste.db"
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO produtos(codigo,codigo_barras,nome,estoque_atual,controla_estoque,permite_estoque_negativo) VALUES(?,?,?,?,?,?)",
            [("A1", "", "PRODUTO A", 20.0, 1, 0), ("B1", "", "PRODUTO B", 5.0, 1, 0)],
        )
        conn.commit()
        conn.close()
        repo = NFeDevolucaoRepository(DatabaseManager(self.db_path))
        self.service = NFeDevolucaoService(repo)
        self.fiscal_auth = SimpleNamespace(
            require_authenticated_actor=lambda action, operation: "gerente"
        )
        self.documento = NFeDocument(
            chave="1" * 44,
            numero="123",
            fornecedor="Empresa Teste",
            cnpj="12345678000199",
            itens=(
                NFeItem(
                    "A1", "Produto A", 10, "UN", 5.0, ncm="11111111", cfop="5102",
                    base_icms=50.0, aliquota_icms=18.0, valor_icms=9.0,
                    base_pis=50.0, aliquota_pis=1.65, valor_pis=0.83,
                    base_cofins=50.0, aliquota_cofins=7.6, valor_cofins=3.8,
                    base_ipi=50.0, aliquota_ipi=5.0, valor_ipi=2.5,
                ),
                NFeItem("B1", "Produto B", 2, "CX", 20.0, ncm="22222222", cfop="5102"),
            ),
            destinatario="Cliente Teste",
            destinatario_documento="98765432000198",
            data_emissao="2026-08-02T10:00:00-03:00",
            serie="1",
            modelo="55",
            valor_total=90.0,
        )
        self.service.registrar_documento(self.documento)

    def tearDown(self):
        self.tmp.cleanup()

    def test_localiza_nota_e_calcula_disponivel(self):
        nota, itens = self.service.localizar_nota("123")
        self.assertEqual(nota["chave"], "1" * 44)
        self.assertEqual([item.quantidade_disponivel for item in itens], [10.0, 2.0])

    def test_sugere_cfop_devolucao_pelo_xml_sem_perguntar_item_a_item(self):
        internal = self.service.sugerir_cfop_devolucao("5102")
        interstate = self.service.sugerir_cfop_devolucao("6102")
        substituted = self.service.sugerir_cfop_devolucao("5405", csosn="500")
        self.assertEqual((internal["suggested"], internal["confidence"]), ("5202", "ALTA"))
        self.assertEqual(interstate["suggested"], "6202")
        self.assertEqual(substituted["suggested"], "5411")
        self.assertIn("5410", substituted["candidates"])

    def test_cfop_desconhecido_oferece_opcoes_e_invalido_exige_revisao(self):
        analysis = self.service.sugerir_cfop_devolucao("5949")
        self.assertEqual(analysis["suggested"], "5202")
        self.assertEqual(analysis["confidence"], "MEDIA")
        self.assertIn("5553", analysis["candidates"])
        invalid = self.service.sugerir_cfop_devolucao("")
        self.assertEqual(invalid["suggested"], "")
        self.assertEqual(invalid["confidence"], "BAIXA")

    def test_cria_devolucao_parcial(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123",
            tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 3)],
            motivo="Defeito",
        )
        rascunho = self.service.repository.buscar_rascunho(devolucao_id)
        self.assertEqual(rascunho["tipo"], "PARCIAL")
        self.assertEqual(rascunho["valor_total"], 15.0)
        _, atualizados = self.service.localizar_nota("123")
        self.assertEqual(atualizados[0].quantidade_disponivel, 7.0)

    def test_calcula_impostos_proporcionais_sem_inventar_aliquotas(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 2)], motivo="Defeito"
        )
        resultado = self.service.calcular_impostos_proporcionais(devolucao_id)
        item = resultado["itens"][0]
        self.assertAlmostEqual(item["proporcao"], 0.2)
        self.assertEqual(item["valor_icms"], 1.8)
        self.assertEqual(item["valor_pis"], 0.17)
        self.assertEqual(item["valor_cofins"], 0.76)
        self.assertEqual(item["valor_ipi"], 0.5)
        self.assertEqual(resultado["totais"]["base_icms"], 10.0)

    def test_cria_devolucao_integral_do_saldo(self):
        _, itens = self.service.localizar_nota("123")
        self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 4)], motivo="Troca"
        )
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="INTEGRAL", selecoes=None, motivo="Devolução integral"
        )
        rascunho = self.service.repository.buscar_rascunho(devolucao_id)
        quantidades = {item["codigo"]: item["quantidade"] for item in rascunho["itens"]}
        self.assertEqual(quantidades, {"A1": 6.0, "B1": 2.0})
        self.assertEqual(rascunho["valor_total"], 70.0)

    def test_bloqueia_quantidade_acima_do_saldo(self):
        _, itens = self.service.localizar_nota("123")
        with self.assertRaisesRegex(ValueError, "Disponível"):
            self.service.criar_rascunho(
                referencia_nota="123", tipo="PARCIAL",
                selecoes=[(itens[0].item_origem_id, 11)], motivo="Erro"
            )

    def test_rejeita_item_de_outra_nota(self):
        with self.assertRaisesRegex(ValueError, "não pertence"):
            self.service.criar_rascunho(
                referencia_nota="123", tipo="PARCIAL",
                selecoes=[(999, 1)], motivo="Erro"
            )

    def test_valida_rascunho_fiscal(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123",
            tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)],
            motivo="Defeito",
        )
        self.assertEqual(self.service.validar_rascunho(devolucao_id), [])

    def test_cancelamento_libera_saldo(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123",
            tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 3)],
            motivo="Troca",
        )
        self.assertTrue(self.service.cancelar_rascunho(devolucao_id))
        _, atualizados = self.service.localizar_nota("123")
        self.assertEqual(atualizados[0].quantidade_disponivel, 10.0)

    def test_nota_com_devolucao_nao_pode_ser_sobrescrita(self):
        _, itens = self.service.localizar_nota("123")
        self.service.criar_rascunho(
            referencia_nota="123",
            tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)],
            motivo="Troca",
        )
        with self.assertRaisesRegex(ValueError, "não pode ser sobrescrita"):
            self.service.registrar_documento(self.documento)

    def test_finaliza_rascunho_e_gera_xml(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 2)], motivo="Defeito",
            observacoes="Produto avariado",
        )
        pasta = Path(self.tmp.name) / "xml"
        caminho = self.service.finalizar_rascunho(devolucao_id, pasta)
        self.assertTrue(caminho.exists())
        conteudo = caminho.read_text(encoding="utf-8")
        self.assertIn("NFeDevolucaoRascunho", conteudo)
        self.assertIn("Produto A", conteudo)
        self.assertIn("Produto avariado", conteudo)
        rascunho = self.service.repository.buscar_rascunho(devolucao_id)
        self.assertEqual(rascunho["status"], "PRONTO")
        self.assertTrue(rascunho["numero_devolucao"].startswith("DEV-"))
        self.assertEqual(len(rascunho["hash_xml"]), 64)
        self.assertEqual(Path(rascunho["xml_rascunho"]), caminho)

    def test_finalizacao_idempotente(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Troca",
        )
        pasta = Path(self.tmp.name) / "xml"
        primeiro = self.service.finalizar_rascunho(devolucao_id, pasta)
        segundo = self.service.finalizar_rascunho(devolucao_id, pasta)
        self.assertEqual(primeiro, segundo)

    def test_rascunho_com_chave_invalida_nao_finaliza(self):
        documento = NFeDocument(
            chave="123", numero="999", fornecedor="Empresa", cnpj="12345678000199",
            itens=(NFeItem("C1", "Produto C", 1, "UN", 10.0, ncm="33333333", cfop="5102"),),
            destinatario="Cliente", destinatario_documento="98765432000198",
        )
        self.service.registrar_documento(documento)
        _, itens = self.service.localizar_nota("999")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="999", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        with self.assertRaisesRegex(ValueError, "44 dígitos"):
            self.service.finalizar_rascunho(devolucao_id, Path(self.tmp.name) / "xml")

    def test_prepara_nfe_oficial_com_referencia_e_finalidade_devolucao(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 2)], motivo="Defeito",
        )
        fiscal = FiscalService(lambda: sqlite3.connect(self.db_path), storage_dir=Path(self.tmp.name) / "fiscal")
        xml, chave = self.service.preparar_documento_fiscal(
            devolucao_id,
            fiscal_service=fiscal,
            issuer={
                "cnpj": "98765432000198", "name": "CLIENTE TESTE", "state": "BA",
                "city_code": "2927408", "state_registration": "123456789",
                "tax_regime_code": 1, "street": "RUA A", "number": "1",
                "district": "CENTRO", "city": "SALVADOR", "zip_code": "40000000",
            },
            document={
                "state_code": "29", "series": 1, "number": 10, "model": "55",
                "environment": "HOMOLOGACAO", "destination": 1,
                "final_consumer": 0, "presence": 0, "payment_code": "90",
                "numeric_code": "12345678",
            },
            item_overrides={itens[0].item_origem_id: {"cfop": "5202", "csosn": "102"}},
        )
        texto = xml.decode("utf-8")
        self.assertEqual(len(chave), 44)
        self.assertIn("<finNFe>4</finNFe>", texto)
        self.assertIn(f"<refNFe>{'1' * 44}</refNFe>", texto)
        self.assertIn("<CFOP>5202</CFOP>", texto)
        self.assertIn("<tPag>90</tPag>", texto)
        self.assertIn("<vPag>0.00</vPag>", texto)

    def test_preparo_oficial_transporta_tributos_proporcionais_para_xml(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 2)], motivo="Defeito",
        )
        fiscal = FiscalService(lambda: sqlite3.connect(self.db_path), storage_dir=Path(self.tmp.name) / "fiscal")
        xml, _ = self.service.preparar_documento_fiscal(
            devolucao_id, fiscal_service=fiscal,
            issuer={
                "cnpj": "98765432000198", "name": "CLIENTE TESTE", "state": "BA",
                "city_code": "2927408", "state_registration": "123456789",
                "tax_regime_code": 3, "street": "RUA A", "number": "1",
                "district": "CENTRO", "city": "SALVADOR", "zip_code": "40000000",
            },
            document={
                "state_code": "29", "series": 1, "number": 11, "model": "55",
                "environment": "HOMOLOGACAO", "destination": 1,
                "final_consumer": 0, "presence": 0, "payment_code": "90",
                "numeric_code": "12345679",
            },
            item_overrides={itens[0].item_origem_id: {"cfop": "5202", "cst": "00"}},
        )
        texto = xml.decode("utf-8")
        self.assertIn("<vICMS>1.80</vICMS>", texto)
        self.assertIn("<vPIS>0.17</vPIS>", texto)
        self.assertIn("<vCOFINS>0.76</vCOFINS>", texto)
        self.assertIn("<vIPIDevol>0.50</vIPIDevol>", texto)
        self.assertIn("<pDevol>20.00</pDevol>", texto)

    def test_preparo_oficial_exige_cfop_confirmado_e_emitente_coerente(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        fiscal = FiscalService(lambda: sqlite3.connect(self.db_path), storage_dir=Path(self.tmp.name) / "fiscal")
        issuer = {
            "cnpj": "98765432000198", "name": "CLIENTE TESTE", "state": "BA",
            "city_code": "2927408", "state_registration": "123", "tax_regime_code": 1,
        }
        document = {"state_code": "29", "series": 1, "number": 11, "numeric_code": "12345678"}
        with self.assertRaisesRegex(ValueError, "CFOP de devolução"):
            self.service.preparar_documento_fiscal(
                devolucao_id, fiscal_service=fiscal, issuer=issuer, document=document
            )
        issuer_errado = dict(issuer, cnpj="11111111000111")
        with self.assertRaisesRegex(ValueError, "destinatário da NF-e original"):
            self.service.preparar_documento_fiscal(
                devolucao_id, fiscal_service=fiscal, issuer=issuer_errado, document=document,
                item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
            )

    def test_revalida_saldo_dentro_da_transacao(self):
        _, itens = self.service.localizar_nota("123")
        item_id = itens[0].item_origem_id
        # Simula duas telas abertas com o mesmo saldo inicial. A segunda gravação
        # deve consultar novamente o banco, não confiar na leitura antiga.
        self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(item_id, 7)], motivo="Primeira devolução",
        )
        with self.assertRaisesRegex(ValueError, "Disponível: 3"):
            self.service.repository.criar_rascunho(
                documento_origem_id=1, tipo="PARCIAL", motivo="Segunda devolução",
                observacoes="",
                itens=[{"item_origem_id": item_id, "quantidade": 4, "valor_unitario": 5}],
            )

    def test_repositorio_rejeita_item_duplicado_na_mesma_devolucao(self):
        _, itens = self.service.localizar_nota("123")
        item_id = itens[0].item_origem_id
        with self.assertRaisesRegex(ValueError, "mais de uma vez"):
            self.service.repository.criar_rascunho(
                documento_origem_id=1, tipo="PARCIAL", motivo="Duplicado",
                observacoes="",
                itens=[
                    {"item_origem_id": item_id, "quantidade": 1, "valor_unitario": 5},
                    {"item_origem_id": item_id, "quantidade": 1, "valor_unitario": 5},
                ],
            )

    def test_historico_lista_estado_fiscal_e_documentos(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Troca",
        )
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, {
                "access_key": "4" * 44, "protocol": "12345",
                "fiscal_record": {"processed_path": "/tmp/processado.xml"},
                "events": [{"event_type": "CCe"}],
            }, status="AUTORIZADA"
        )
        historico = self.service.listar_historico()
        registro = next(item for item in historico if int(item["id"]) == devolucao_id)
        self.assertEqual(registro["fiscal_status"], "AUTORIZADA")
        self.assertEqual(registro["access_key"], "4" * 44)
        self.assertEqual(registro["protocol"], "12345")
        self.assertEqual(registro["fiscal_record"]["processed_path"], "/tmp/processado.xml")
        self.assertEqual(len(registro["events"]), 1)

    def test_cancelado_nao_finaliza(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Troca",
        )
        self.service.cancelar_rascunho(devolucao_id)
        with self.assertRaisesRegex(ValueError, "cancelado"):
            self.service.finalizar_rascunho(devolucao_id, Path(self.tmp.name) / "xml")

    def test_emissao_oficial_registra_autorizacao_e_protocolo(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )

        class FiscalFake:
            def build_document_xml(self, **kwargs):
                return b"<NFe><infNFe Id='NFe" + b"2" * 44 + b"'/></NFe>", "2" * 44
            def authorize_document(self, **kwargs):
                response = SimpleNamespace(success=True, protocol="12345", status_code="100", message="Autorizado")
                return response, {"processed_path": str(Path(self_dir) / "proc.xml"), "actor": "gerente"}

        self_dir = self.tmp.name
        state = self.service.emitir_devolucao_oficial(
            devolucao_id, fiscal_service=FiscalFake(), issuer={"cnpj": "98765432000198"},
            document={}, item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
            password="senha",
        )
        self.assertEqual(state["status"], "AUTORIZADA")
        self.assertEqual(state["protocol"], "12345")
        self.assertEqual(self.service.repository.buscar_rascunho(devolucao_id)["status"], "AUTORIZADA")
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(
            conn.execute(
                "SELECT usuario FROM estoque_movimentacoes "
                "WHERE origem='DEVOLUCAO_NFE'"
            ).fetchone()[0],
            "gerente",
        )
        conn.close()

    def test_emissao_nao_aceita_actor_livre(self):
        with self.assertRaisesRegex(TypeError, "actor"):
            self.service.emitir_devolucao_oficial(
                1, fiscal_service=object(), issuer={}, document={},
                item_overrides={}, password="senha", actor="forjado",
            )

    def test_autorizacao_sem_actor_autenticado_nao_baixa_estoque(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )

        class FiscalSemActor:
            def build_document_xml(self, **kwargs):
                return b"<NFe/>", "2" * 44

            def authorize_document(self, **kwargs):
                return SimpleNamespace(
                    success=True, protocol="12345", status_code="100",
                    message="Autorizado",
                ), {}

        with self.assertRaisesRegex(RuntimeError, "autoria técnica autenticada"):
            self.service.emitir_devolucao_oficial(
                devolucao_id, fiscal_service=FiscalSemActor(),
                issuer={"cnpj": "98765432000198"}, document={},
                item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
                password="senha",
            )
        self.assertEqual(
            self.service.estado_fiscal(devolucao_id)["status"],
            "AUTORIZADA_PENDENTE_ESTOQUE",
        )
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM estoque_movimentacoes "
                "WHERE origem='DEVOLUCAO_NFE'"
            ).fetchone()[0],
            0,
        )
        conn.close()

    def test_rejeicao_fiscal_fica_registrada_sem_autorizar(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )

        class FiscalFake:
            def build_document_xml(self, **kwargs):
                return b"<NFe/>", "3" * 44
            def authorize_document(self, **kwargs):
                response = SimpleNamespace(success=False, protocol="", status_code="539", message="Duplicidade")
                return response, {}

        state = self.service.emitir_devolucao_oficial(
            devolucao_id, fiscal_service=FiscalFake(), issuer={"cnpj": "98765432000198"},
            document={}, item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
            password="senha",
        )
        self.assertEqual(state["status"], "REJEITADA")
        self.assertEqual(state["status_code"], "539")

    def test_cancelamento_oficial_so_muda_status_quando_aceito(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, {"access_key": "4" * 44, "protocol": "123", "events": []}, status="AUTORIZADA"
        )

        class FiscalFake:
            def send_event(self, **kwargs):
                return SimpleNamespace(success=True, status_code="135", message="Evento registrado"), {"event_type": "CANCELAMENTO", "actor": "gerente"}

        state = self.service.cancelar_devolucao_oficial(
            devolucao_id, fiscal_service=FiscalFake(), password="senha",
            justification="Cancelamento solicitado pelo cliente",
        )
        self.assertEqual(state["status"], "CANCELADA")
        self.assertEqual(len(state["events"]), 1)

    def test_cancelamento_nao_aceita_actor_livre(self):
        with self.assertRaisesRegex(TypeError, "actor"):
            self.service.cancelar_devolucao_oficial(
                1, fiscal_service=object(), password="senha",
                justification="Cancelamento solicitado pelo cliente",
                actor="forjado",
            )

    def test_evento_sem_actor_autenticado_nao_reverte_estoque(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        self.service.repository.salvar_estado_fiscal(
            devolucao_id,
            {"access_key": "4" * 44, "protocol": "123", "events": []},
            status="AUTORIZADA",
        )

        class FiscalSemActor:
            def send_event(self, **kwargs):
                return SimpleNamespace(
                    success=True, status_code="135", message="Evento registrado"
                ), {"event_type": "CANCELAMENTO"}

        with self.assertRaisesRegex(RuntimeError, "autoria técnica autenticada"):
            self.service.cancelar_devolucao_oficial(
                devolucao_id, fiscal_service=FiscalSemActor(), password="senha",
                justification="Cancelamento solicitado pelo cliente",
            )
        self.assertEqual(
            self.service.estado_fiscal(devolucao_id)["status"],
            "CANCELADA_PENDENTE_ESTOQUE",
        )
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM estoque_movimentacoes "
                "WHERE origem='CANCELAMENTO_DEVOLUCAO_NFE'"
            ).fetchone()[0],
            0,
        )
        conn.close()


    def test_devolucao_cancelada_nao_pode_ser_reautorizada(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, {"access_key": "4" * 44, "protocol": "123", "events": []}, status="CANCELADA"
        )

        class FiscalFake:
            def build_document_xml(self, **kwargs):
                return b"<NFe/>", "5" * 44
            def authorize_document(self, **kwargs):
                raise AssertionError("não deveria transmitir")

        with self.assertRaisesRegex(ValueError, "cancelada"):
            self.service.emitir_devolucao_oficial(
                devolucao_id, fiscal_service=FiscalFake(), issuer={"cnpj": "98765432000198"},
                document={}, item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
                password="senha",
            )

    def test_tentativas_fiscais_preservam_rejeicao_e_erro(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )

        class FiscalRejeita:
            def build_document_xml(self, **kwargs):
                return b"<NFe>rejeitada</NFe>", "6" * 44
            def authorize_document(self, **kwargs):
                response = SimpleNamespace(success=False, protocol="", status_code="539", message="Duplicidade")
                return response, {}

        state = self.service.emitir_devolucao_oficial(
                devolucao_id, fiscal_service=FiscalRejeita(), issuer={"cnpj": "98765432000198"},
            document={}, item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
            password="senha",
        )
        self.assertEqual(state["attempts"][-1]["result"], "REJEITADA")
        self.assertEqual(state["attempts"][-1]["status_code"], "539")
        self.assertEqual(len(state["attempts"][-1]["request_sha256"]), 64)

        class FiscalFalha:
            def build_document_xml(self, **kwargs):
                return b"<NFe>erro</NFe>", "7" * 44
            def authorize_document(self, **kwargs):
                raise RuntimeError("SEFAZ indisponível")

        with self.assertRaisesRegex(RuntimeError, "indisponível"):
            self.service.emitir_devolucao_oficial(
                devolucao_id, fiscal_service=FiscalFalha(), issuer={"cnpj": "98765432000198"},
                document={}, item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
                password="senha",
            )
        final_state = self.service.estado_fiscal(devolucao_id)
        self.assertEqual(final_state["status"], "ERRO_FISCAL")
        self.assertEqual(len(final_state["attempts"]), 2)
        self.assertEqual(final_state["attempts"][-1]["result"], "ERRO")
        self.assertIn("indisponível", final_state["attempts"][-1]["message"])



    def test_autorizacao_baixa_estoque_e_cancelamento_reverte(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 2)], motivo="Defeito",
        )

        class FiscalAutoriza:
            def build_document_xml(self, **kwargs):
                return b"<NFe><infNFe Id='NFe" + b"8" * 44 + b"'/></NFe>", "8" * 44
            def authorize_document(self, **kwargs):
                return SimpleNamespace(success=True, protocol="888", status_code="100", message="Autorizado"), {"actor": "gerente"}
            def send_event(self, **kwargs):
                return SimpleNamespace(success=True, status_code="135", message="Cancelado"), {"event_type": "CANCELAMENTO", "actor": "gerente"}

        fiscal = FiscalAutoriza()
        state = self.service.emitir_devolucao_oficial(
            devolucao_id, fiscal_service=fiscal, issuer={"cnpj": "98765432000198"},
            document={}, item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
            password="senha",
        )
        self.assertEqual(state["status"], "AUTORIZADA")
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE codigo='A1'").fetchone()[0], 18.0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM estoque_movimentacoes WHERE origem='DEVOLUCAO_NFE'").fetchone()[0], 1)
        conn.close()

        cancelled = self.service.cancelar_devolucao_oficial(
            devolucao_id, fiscal_service=fiscal, password="senha",
            justification="Cancelamento por erro operacional",
        )
        self.assertEqual(cancelled["status"], "CANCELADA")
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE codigo='A1'").fetchone()[0], 20.0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM estoque_movimentacoes WHERE origem='CANCELAMENTO_DEVOLUCAO_NFE'").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT usuario FROM estoque_movimentacoes WHERE origem='CANCELAMENTO_DEVOLUCAO_NFE'").fetchone()[0], "gerente")
        conn.close()

    def test_autorizacao_com_estoque_insuficiente_fica_pendente(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 3)], motivo="Defeito",
        )
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE produtos SET estoque_atual=1 WHERE codigo='A1'")
        conn.commit(); conn.close()

        class FiscalAutoriza:
            def build_document_xml(self, **kwargs):
                return b"<NFe><infNFe Id='NFe" + b"9" * 44 + b"'/></NFe>", "9" * 44
            def authorize_document(self, **kwargs):
                return SimpleNamespace(success=True, protocol="999", status_code="100", message="Autorizado"), {"actor": "gerente"}

        with self.assertRaisesRegex(RuntimeError, "baixa de estoque falhou"):
            self.service.emitir_devolucao_oficial(
                devolucao_id, fiscal_service=FiscalAutoriza(), issuer={"cnpj": "98765432000198"},
                document={}, item_overrides={itens[0].item_origem_id: {"cfop": "5202"}},
                password="senha",
            )
        self.assertEqual(self.service.estado_fiscal(devolucao_id)["status"], "AUTORIZADA_PENDENTE_ESTOQUE")
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE codigo='A1'").fetchone()[0], 1.0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM estoque_movimentacoes").fetchone()[0], 0)
        conn.close()

    def test_recupera_baixa_de_estoque_pendente_de_forma_idempotente(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 2)], motivo="Defeito",
        )
        estado = {"status": "AUTORIZADA_PENDENTE_ESTOQUE", "access_key": "8" * 44}
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, estado, status="AUTORIZADA_PENDENTE_ESTOQUE"
        )
        recuperado = self.service.recuperar_efeito_estoque_pendente(
            devolucao_id, fiscal_service=self.fiscal_auth
        )
        self.assertEqual(recuperado["status"], "AUTORIZADA")
        novamente = self.service.recuperar_efeito_estoque_pendente(
            devolucao_id, fiscal_service=self.fiscal_auth
        )
        self.assertEqual(novamente["status"], "AUTORIZADA")
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE codigo='A1'").fetchone()[0], 18.0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM estoque_movimentacoes WHERE origem='DEVOLUCAO_NFE'").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT usuario FROM estoque_movimentacoes WHERE origem='DEVOLUCAO_NFE'").fetchone()[0], "gerente")
        conn.close()

    def test_recuperacao_nao_aceita_actor_livre(self):
        with self.assertRaisesRegex(TypeError, "actor"):
            self.service.recuperar_efeito_estoque_pendente(
                1, fiscal_service=self.fiscal_auth, actor="forjado"
            )

    def test_recuperacao_falha_fechado_antes_de_alterar_estoque(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, {}, status="AUTORIZADA_PENDENTE_ESTOQUE"
        )

        class FiscalSemPermissao:
            def require_authenticated_actor(self, action, *, operation):
                raise PermissionError("sessão fiscal obrigatória")

        with self.assertRaisesRegex(PermissionError, "sessão fiscal"):
            self.service.recuperar_efeito_estoque_pendente(
                devolucao_id, fiscal_service=FiscalSemPermissao()
            )
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM estoque_movimentacoes "
                "WHERE origem='DEVOLUCAO_NFE'"
            ).fetchone()[0],
            0,
        )
        conn.close()

    def test_recupera_reversao_pendente_apos_cancelamento(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 2)], motivo="Defeito",
        )
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, {"status": "AUTORIZADA_PENDENTE_ESTOQUE"},
            status="AUTORIZADA_PENDENTE_ESTOQUE",
        )
        self.service.recuperar_efeito_estoque_pendente(
            devolucao_id, fiscal_service=self.fiscal_auth
        )
        estado = self.service.estado_fiscal(devolucao_id)
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, estado, status="CANCELADA_PENDENTE_ESTOQUE"
        )
        recuperado = self.service.recuperar_efeito_estoque_pendente(
            devolucao_id, fiscal_service=self.fiscal_auth
        )
        self.assertEqual(recuperado["status"], "CANCELADA")
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT estoque_atual FROM produtos WHERE codigo='A1'").fetchone()[0], 20.0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM estoque_movimentacoes WHERE origem='CANCELAMENTO_DEVOLUCAO_NFE'").fetchone()[0], 1)
        conn.close()

    def test_estado_autorizado_pendente_bloqueia_reemissao(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, {"status": "AUTORIZADA_PENDENTE_ESTOQUE"},
            status="AUTORIZADA_PENDENTE_ESTOQUE",
        )
        class FiscalNaoDeveChamar:
            def build_document_xml(self, **kwargs):
                raise AssertionError("não deveria gerar novo XML")
        with self.assertRaisesRegex(ValueError, "já possui NF-e autorizada"):
            self.service.emitir_devolucao_oficial(
                devolucao_id, fiscal_service=FiscalNaoDeveChamar(), issuer={}, document={},
                item_overrides={}, password="x",
            )

    def test_cancelamento_oficial_aceita_autorizada_pendente_sem_estoque_aplicado(self):
        _, itens = self.service.localizar_nota("123")
        devolucao_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        self.service.repository.salvar_estado_fiscal(
            devolucao_id, {"status": "AUTORIZADA_PENDENTE_ESTOQUE", "access_key": "8" * 44, "protocol": "123"},
            status="AUTORIZADA_PENDENTE_ESTOQUE",
        )
        class FiscalCancela:
            def send_event(self, **kwargs):
                return SimpleNamespace(success=True, status_code="135", message="Cancelado"), {"event_type": "CANCELAMENTO", "actor": "gerente"}
        estado = self.service.cancelar_devolucao_oficial(
            devolucao_id, fiscal_service=FiscalCancela(), password="x",
            justification="Cancelamento por erro operacional",
        )
        self.assertEqual(estado["status"], "CANCELADA")
        self.assertEqual(estado["stock_reversal"]["status"], "NAO_APLICADO")

    def test_recuperacao_em_lote_preserva_falhas_e_conclui_validas(self):
        _, itens = self.service.localizar_nota("123")
        ok_id = self.service.criar_rascunho(
            referencia_nota="123", tipo="PARCIAL",
            selecoes=[(itens[0].item_origem_id, 1)], motivo="Defeito",
        )
        self.service.repository.salvar_estado_fiscal(ok_id, {}, status="AUTORIZADA_PENDENTE_ESTOQUE")
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE produtos SET estoque_atual=0 WHERE codigo='A1'")
        conn.commit(); conn.close()
        resultado = self.service.recuperar_pendencias_estoque(
            fiscal_service=self.fiscal_auth
        )
        self.assertEqual(resultado["concluidas"], [])
        self.assertEqual(resultado["falhas"][0]["devolucao_id"], ok_id)
        self.assertEqual(self.service.estado_fiscal(ok_id)["status"], "AUTORIZADA_PENDENTE_ESTOQUE")
        self.assertIn("estoque insuficiente", self.service.estado_fiscal(ok_id)["last_error"].lower())



class NFeDevolucaoUIIntegrationTests(unittest.TestCase):
    def test_historico_oferece_emissao_e_cancelamento_oficial(self):
        source = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn('text="Emitir oficial"', source)
        self.assertIn('text="Cancelar oficial"', source)
        self.assertIn("emitir_devolucao_oficial", source)
        self.assertIn("cancelar_devolucao_oficial", source)
        self.assertIn("reserve_number", source)
        self.assertIn("release_number", source)
        self.assertIn("recuperar_efeito_estoque_pendente", source)
        self.assertIn('text="Recuperar estoque"', source)

    def test_configuracao_fiscal_expoe_dados_do_emitente(self):
        source = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")
        for label in (
            "Razão social do emitente", "Inscrição estadual", "Código IBGE do município",
            "Série padrão para NF-e de devolução",
        ):
            self.assertIn(label, source)

if __name__ == "__main__":
    unittest.main()
