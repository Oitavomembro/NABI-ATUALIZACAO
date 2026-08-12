import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from repositories import EstoqueRepository
from services import EstoqueService


SCHEMA = """
CREATE TABLE produtos (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 codigo TEXT NOT NULL UNIQUE,
 nome TEXT NOT NULL,
 tipo_produto TEXT NOT NULL DEFAULT 'MERCADORIA',
 controla_estoque INTEGER NOT NULL DEFAULT 1,
 estoque_atual REAL NOT NULL DEFAULT 0,
 estoque_minimo REAL NOT NULL DEFAULT 0,
 permite_estoque_negativo INTEGER NOT NULL DEFAULT 0,
 ativo INTEGER NOT NULL DEFAULT 1,
 atualizado_em TEXT NOT NULL DEFAULT ''
);
CREATE TABLE estoque_movimentacoes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 produto_id INTEGER NOT NULL,
 tipo TEXT NOT NULL,
 quantidade REAL NOT NULL,
 saldo_anterior REAL NOT NULL,
 saldo_atual REAL NOT NULL,
 origem TEXT NOT NULL DEFAULT '',
 origem_id TEXT NOT NULL DEFAULT '',
 motivo TEXT NOT NULL DEFAULT '',
 usuario TEXT NOT NULL DEFAULT 'Sistema',
 data TEXT NOT NULL,
 FOREIGN KEY(produto_id) REFERENCES produtos(id)
);
CREATE UNIQUE INDEX idx_estoque_mov_origem_produto
ON estoque_movimentacoes(origem, origem_id, produto_id)
WHERE origem<>'' AND origem_id<>'';
"""


class EstoqueServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "estoque.db"
        conn = sqlite3.connect(self.path)
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO produtos(codigo,nome,estoque_atual,estoque_minimo) VALUES('P1','Produto 1',10,3)"
        )
        conn.execute(
            "INSERT INTO produtos(codigo,nome,tipo_produto,controla_estoque) VALUES('S1','Serviço','SERVICO',0)"
        )
        conn.commit()
        conn.close()
        self.database = DatabaseManager(self.path)
        self.repository = EstoqueRepository(self.database)
        self.service = EstoqueService(self.repository)

    def tearDown(self):
        self.temp.cleanup()

    def test_entrada_saida_e_historico(self):
        entrada = self.service.entrada(1, 5, origem="COMPRA", origem_id="10")
        self.assertEqual(entrada.saldo_anterior, 10)
        self.assertEqual(entrada.saldo_atual, 15)
        saida = self.service.saida(1, 4, origem="AJUSTE_MANUAL")
        self.assertEqual(saida.saldo_atual, 11)
        movimentos = self.repository.listar_movimentacoes(1)
        self.assertEqual(len(movimentos), 2)
        self.assertEqual(movimentos[0]["tipo"], "SAIDA")

    def test_entrada_idempotente_por_origem(self):
        primeira = self.service.entrada_idempotente(
            1, 5, origem="NFE_XML", origem_id="CHAVE:0"
        )
        segunda = self.service.entrada_idempotente(
            1, 5, origem="NFE_XML", origem_id="CHAVE:0"
        )
        self.assertIsNotNone(primeira)
        self.assertIsNone(segunda)
        self.assertEqual(self.service.saldo(1), 15)
        self.assertEqual(len(self.repository.listar_movimentacoes(1)), 1)

    def test_saida_sem_saldo_reverte(self):
        with self.assertRaisesRegex(ValueError, "Estoque insuficiente"):
            self.service.saida(1, 11, origem="VENDA", origem_id="99")
        self.assertEqual(self.service.saldo(1), 10)
        self.assertEqual(len(self.repository.listar_movimentacoes(1)), 0)

    def test_baixa_venda_agrega_produto_repetido_e_e_idempotente(self):
        itens = [
            {"produto_id": 1, "qtd": 2},
            {"produto_id": 1, "qtd": 3},
            {"produto_id": None, "qtd": 100},
        ]
        primeira = self.service.baixar_itens_venda(itens, venda_id=123)
        segunda = self.service.baixar_itens_venda(itens, venda_id=123)
        self.assertEqual(len(primeira), 1)
        self.assertEqual(segunda, [])
        self.assertEqual(self.service.saldo(1), 5)
        movimento = self.repository.listar_movimentacoes(1)[0]
        self.assertEqual(movimento["quantidade"], -5)

    def test_baixa_venda_permite_saldo_negativo_quando_pdv_autorizou(self):
        resultado = self.service.baixar_itens_venda(
            [{"produto_id": 1, "qtd": 12, "estoque_override": True}],
            venda_id=124,
        )
        self.assertEqual(len(resultado), 1)
        self.assertEqual(self.service.saldo(1), -2)
        movimento = self.repository.listar_movimentacoes(1)[0]
        self.assertIn("autorizado no PDV", movimento["motivo"])

    def test_estorno_venda_idempotente(self):
        self.service.baixar_itens_venda([{"produto_id": 1, "qtd": 4}], venda_id=200)
        primeiro = self.service.estornar_venda(200)
        segundo = self.service.estornar_venda(200)
        self.assertEqual(len(primeiro), 1)
        self.assertEqual(segundo, [])
        self.assertEqual(self.service.saldo(1), 10)

    def test_ajuste_exige_motivo(self):
        with self.assertRaisesRegex(ValueError, "motivo"):
            self.service.ajustar(1, 8, motivo="")
        resultado = self.service.ajustar(1, 8, motivo="Contagem física")
        self.assertEqual(resultado.saldo_atual, 8)
        self.assertEqual(resultado.quantidade, -2)

    def test_servico_nao_movimenta_estoque(self):
        with self.assertRaisesRegex(ValueError, "não controla estoque"):
            self.service.entrada(2, 1, origem="AJUSTE")

    def test_lista_abaixo_minimo(self):
        self.service.ajustar(1, 2, motivo="Inventário")
        criticos = self.repository.listar_abaixo_minimo()
        self.assertEqual([item["codigo"] for item in criticos], ["P1"])

    def test_inventario_lote_cria_snapshot_e_ajusta_transacionalmente(self):
        resultado = self.service.inventario_lote(
            [{"produto_id": 1, "contagem_fisica": 7}],
            motivo="Inventário mensal",
            usuario="Operador",
            diretorio_snapshot=Path(self.temp.name) / "snapshots",
        )
        self.assertTrue(Path(resultado.snapshot_path).exists())
        self.assertEqual(self.service.saldo(1), 7)
        self.assertEqual(len(resultado.movimentacoes), 1)
        movimento = self.repository.listar_movimentacoes(1)[0]
        self.assertEqual(movimento["origem"], "INVENTARIO")
        self.assertEqual(movimento["usuario"], "Operador")

    def test_inventario_lote_valida_tudo_antes_de_alterar(self):
        with self.assertRaisesRegex(ValueError, "não encontrado"):
            self.service.inventario_lote(
                [
                    {"produto_id": 1, "contagem_fisica": 5},
                    {"produto_id": 999, "contagem_fisica": 2},
                ],
                motivo="Contagem",
                diretorio_snapshot=Path(self.temp.name) / "snapshots",
            )
        self.assertEqual(self.service.saldo(1), 10)
        self.assertEqual(self.repository.listar_movimentacoes(1), [])

    def test_diagnostico_detecta_saldo_sem_historico_e_divergente(self):
        divergencias = self.service.diagnosticar_divergencias()
        self.assertEqual(divergencias[0]["tipo"], "SEM_HISTORICO")
        self.service.ajustar(1, 8, motivo="Ajuste inicial")
        with self.database.session(write=True) as connection:
            connection.execute("UPDATE produtos SET estoque_atual=6 WHERE id=1")
        divergencias = self.service.diagnosticar_divergencias()
        self.assertEqual(divergencias[0]["tipo"], "SALDO_DIVERGENTE")
        self.assertEqual(divergencias[0]["saldo_historico"], 8)

    def test_reverter_ajuste_e_idempotente(self):
        ajuste = self.service.ajustar(1, 8, motivo="Contagem física")
        reversao = self.service.reverter_movimentacao(ajuste.movimentacao_id, motivo="Contagem incorreta")
        repetida = self.service.reverter_movimentacao(ajuste.movimentacao_id, motivo="Repetição")
        self.assertEqual(reversao.saldo_atual, 10)
        self.assertIsNone(repetida)
        self.assertEqual(self.service.saldo(1), 10)

    def test_reversao_bloqueia_movimento_vinculado(self):
        venda = self.service.saida(1, 2, origem="VENDA", origem_id="55")
        with self.assertRaisesRegex(ValueError, "documento de origem"):
            self.service.reverter_movimentacao(venda.movimentacao_id, motivo="Tentativa manual")
        self.assertEqual(self.service.saldo(1), 8)


if __name__ == "__main__":
    unittest.main()
