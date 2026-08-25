import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from repositories import FinanceiroRepository
from services import FinanceiroService


SCHEMA = """
CREATE TABLE auditoria (
 id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, usuario TEXT, modulo TEXT,
 acao TEXT, objeto TEXT, detalhes TEXT, resultado TEXT
);
CREATE TABLE titulos_financeiros (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tipo TEXT NOT NULL CHECK(tipo IN ('PAGAR','RECEBER')),
 origem TEXT NOT NULL DEFAULT 'MANUAL', origem_id TEXT NOT NULL DEFAULT '',
 pessoa_id INTEGER, pessoa_nome TEXT NOT NULL DEFAULT '', documento TEXT NOT NULL DEFAULT '',
 descricao TEXT NOT NULL DEFAULT '', data_emissao TEXT NOT NULL, data_vencimento TEXT NOT NULL,
 valor_original REAL NOT NULL DEFAULT 0, valor_pago REAL NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'ABERTO' CHECK(status IN ('ABERTO','PARCIAL','PAGO','CANCELADO')),
 observacao TEXT NOT NULL DEFAULT '', criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_titulos_origem_unica
ON titulos_financeiros(tipo,origem,origem_id,documento)
WHERE origem_id<>'' AND status<>'CANCELADO';
CREATE TABLE configuracoes (id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE, valor TEXT);
CREATE TABLE pagamentos_titulos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, titulo_id INTEGER NOT NULL, valor REAL NOT NULL,
 forma_pagamento TEXT NOT NULL DEFAULT '', observacao TEXT NOT NULL DEFAULT '',
 usuario TEXT NOT NULL DEFAULT 'Sistema', data_pagamento TEXT NOT NULL
);
CREATE TABLE movimentacoes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT, descricao TEXT,
 valor REAL, data TEXT, vencimento TEXT, status_pagamento TEXT DEFAULT 'PENDENTE',
 valor_aberto REAL, origem_sistema TEXT DEFAULT '', origem_id TEXT DEFAULT '',
 forma_pagamento TEXT DEFAULT ''
);
"""


class FinanceiroServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "financeiro.db")
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA)
        conn.close()
        self.database = DatabaseManager(self.db_path)
        self.repo = FinanceiroRepository(self.database)
        self.service = FinanceiroService(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_cria_titulo_e_evitar_duplicidade_por_origem(self):
        primeiro = self.service.criar_titulo(
            tipo="PAGAR", valor="150,00".replace(",", "."), data_vencimento="10/08/2026",
            origem="COMPRA", origem_id="1", documento="NF-10", pessoa_nome="Fornecedor",
        )
        segundo = self.service.criar_titulo(
            tipo="PAGAR", valor=999, data_vencimento="2026-08-10",
            origem="COMPRA", origem_id="1", documento="NF-10", pessoa_nome="Fornecedor",
        )
        self.assertEqual(primeiro, segundo)
        self.assertEqual(len(self.repo.listar_titulos()), 1)

    def test_pagamento_parcial_e_total(self):
        titulo_id = self.service.criar_titulo(tipo="RECEBER", valor=100, data_vencimento="2026-08-20")
        parcial = self.service.pagar(titulo_id, 40, forma_pagamento="PIX")
        self.assertEqual(parcial.status, "PARCIAL")
        self.assertEqual(parcial.saldo_aberto, 60.0)
        total = self.service.pagar(titulo_id, 60, forma_pagamento="DINHEIRO")
        self.assertEqual(total.status, "PAGO")
        self.assertEqual(total.saldo_aberto, 0.0)
        self.assertEqual(len(self.repo.listar_pagamentos(titulo_id)), 2)

    def test_impede_pagamento_acima_saldo(self):
        titulo_id = self.service.criar_titulo(tipo="PAGAR", valor=50, data_vencimento="2026-08-20")
        with self.assertRaisesRegex(ValueError, "excede"):
            self.service.pagar(titulo_id, 50.01)

    def test_cancelamento_sem_pagamento(self):
        titulo_id = self.service.criar_titulo(tipo="PAGAR", valor=50, data_vencimento="2026-08-20")
        self.service.cancelar(titulo_id)
        self.assertEqual(self.repo.obter_titulo(titulo_id)["status"], "CANCELADO")

    def test_falha_auditoria_reverte_cancelamento(self):
        titulo_id = self.service.criar_titulo(
            tipo="PAGAR", valor=50, data_vencimento="2026-08-20"
        )
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            "CREATE TRIGGER bloquear_auditoria BEFORE INSERT ON auditoria "
            "WHEN NEW.acao='CANCELAR_TITULO' "
            "BEGIN SELECT RAISE(ABORT, 'auditoria indisponivel'); END"
        )
        connection.close()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "auditoria indisponivel"):
            self.service.cancelar(titulo_id)
        self.assertEqual(self.repo.obter_titulo(titulo_id)["status"], "ABERTO")

    def test_nao_cancela_titulo_com_pagamento(self):
        titulo_id = self.service.criar_titulo(tipo="PAGAR", valor=50, data_vencimento="2026-08-20")
        self.service.pagar(titulo_id, 10)
        with self.assertRaisesRegex(ValueError, "pagamento"):
            self.service.cancelar(titulo_id)

    def test_validacoes(self):
        with self.assertRaises(ValueError):
            self.service.criar_titulo(tipo="OUTRO", valor=1, data_vencimento="2026-08-20")
        with self.assertRaises(ValueError):
            self.service.criar_titulo(tipo="PAGAR", valor=0, data_vencimento="2026-08-20")
        with self.assertRaises(ValueError):
            self.service.criar_titulo(tipo="PAGAR", valor=1, data_vencimento="data ruim")

    def test_fluxo_caixa_e_dre(self):
        receber = self.service.criar_titulo(tipo="RECEBER", valor=200, data_vencimento="2026-08-20", data_emissao="2026-08-01")
        pagar = self.service.criar_titulo(tipo="PAGAR", valor=80, data_vencimento="2026-08-20", data_emissao="2026-08-01")
        self.service.pagar(receber, 150, data_pagamento="2026-08-10")
        self.service.pagar(pagar, 50, data_pagamento="2026-08-10")
        fluxo = self.service.fluxo_caixa("2026-08-01", "2026-08-31")
        self.assertEqual(fluxo["entradas"], 150.0)
        self.assertEqual(fluxo["saidas"], 50.0)
        self.assertEqual(fluxo["saldo"], 100.0)
        dre = self.service.dre("2026-08-01", "2026-08-31")
        self.assertEqual(dre["resultado_competencia"], 120.0)
        self.assertEqual(dre["resultado_realizado"], 100.0)

    def test_juros_multa_centro_custo_e_conciliacao(self):
        titulo = self.service.criar_titulo(tipo="PAGAR", valor=100, data_vencimento="2026-07-01")
        calculo = self.service.calcular_juros_multa(titulo, data_referencia="2026-07-31", multa_percentual=2, juros_mensal_percentual=3)
        self.assertEqual(calculo["dias_atraso"], 30)
        self.assertEqual(calculo["total"], 105.0)
        self.service.definir_centro_custo(titulo, "Administrativo")
        self.assertEqual(self.service.obter_centro_custo(titulo), "ADMINISTRATIVO")
        pagamento = self.service.pagar(titulo, 20)
        self.service.conciliar_pagamento(pagamento.pagamento_id, "EXTRATO-1")

    def test_recorrencia_idempotente_por_competencia(self):
        self.service.criar_recorrencia(identificador="ALUGUEL", tipo="PAGAR", valor=1000, dia_vencimento=31, descricao="Aluguel")
        primeiro = self.service.gerar_recorrencias(2026, 2)
        segundo = self.service.gerar_recorrencias(2026, 2)
        self.assertEqual(primeiro, segundo)
        titulo = self.repo.obter_titulo(primeiro[0])
        self.assertEqual(titulo["data_vencimento"], "2026-02-28")

    def test_dre_realizada_considera_data_do_pagamento(self):
        antigo = self.service.criar_titulo(tipo="RECEBER", valor=100, data_vencimento="2026-08-10", data_emissao="2026-07-01")
        futuro = self.service.criar_titulo(tipo="RECEBER", valor=50, data_vencimento="2026-09-10", data_emissao="2026-08-01")
        self.service.pagar(antigo, 100, data_pagamento="2026-08-05")
        self.service.pagar(futuro, 50, data_pagamento="2026-09-05")
        dre = self.service.dre("2026-08-01", "2026-08-31")
        self.assertEqual(dre["receitas_competencia"], 50.0)
        self.assertEqual(dre["receitas_realizadas"], 100.0)

    def test_baixa_com_encargos_incorpora_juros_e_multa(self):
        titulo = self.service.criar_titulo(tipo="PAGAR", valor=100, data_vencimento="2026-07-01")
        resultado = self.service.baixar_com_encargos(
            titulo, data_pagamento="2026-07-31", multa_percentual=2, juros_mensal_percentual=3,
        )
        atualizado = self.repo.obter_titulo(titulo)
        self.assertEqual(resultado.status, "PAGO")
        self.assertEqual(atualizado["valor_original"], 105.0)
        self.assertEqual(atualizado["valor_pago"], 105.0)
        self.assertEqual(self.repo.listar_pagamentos(titulo)[0]["valor"], 105.0)

    def test_estorno_pagamento_reabre_titulo_e_remove_conciliacao(self):
        titulo = self.service.criar_titulo(tipo="RECEBER", valor=100, data_vencimento="2026-08-10")
        pagamento = self.service.pagar(titulo, 40)
        self.service.conciliar_pagamento(pagamento.pagamento_id, "EXTRATO-X")
        resultado = self.service.estornar_pagamento(pagamento.pagamento_id)
        self.assertEqual(resultado.status, "ABERTO")
        self.assertEqual(self.repo.obter_titulo(titulo)["valor_pago"], 0.0)
        self.assertEqual(self.repo.listar_pagamentos(titulo), [])
        self.assertFalse(any(i["id"] == pagamento.pagamento_id for i in self.service.listar_conciliacoes()))

    def test_gerenciamento_recorrencias(self):
        self.service.criar_recorrencia(identificador="NET", tipo="PAGAR", valor=99, dia_vencimento=10)
        self.assertTrue(self.service.listar_recorrencias()[0]["ativo"])
        self.service.ativar_recorrencia("NET", False)
        self.assertFalse(self.service.listar_recorrencias()[0]["ativo"])
        self.assertEqual(self.service.gerar_recorrencias(2026, 8), [])
        self.service.excluir_recorrencia("NET")
        self.assertEqual(self.service.listar_recorrencias(), [])

    def test_conciliacao_pode_ser_listada_e_desfeita(self):
        titulo = self.service.criar_titulo(tipo="PAGAR", valor=20, data_vencimento="2026-08-10")
        pagamento = self.service.pagar(titulo, 20)
        self.service.conciliar_pagamento(pagamento.pagamento_id, "BANCO-20")
        item = next(i for i in self.service.listar_conciliacoes() if i["id"] == pagamento.pagamento_id)
        self.assertTrue(item["conciliado"])
        self.service.desfazer_conciliacao(pagamento.pagamento_id)
        item = next(i for i in self.service.listar_conciliacoes() if i["id"] == pagamento.pagamento_id)
        self.assertFalse(item["conciliado"])

    def test_estorno_baixa_com_encargos_reverte_valor_original(self):
        titulo = self.service.criar_titulo(tipo="PAGAR", valor=100, data_vencimento="2026-07-01")
        baixa = self.service.baixar_com_encargos(
            titulo, data_pagamento="2026-07-31", multa_percentual=2, juros_mensal_percentual=3,
        )
        resultado = self.service.estornar_pagamento(baixa.pagamento_id)
        atualizado = self.repo.obter_titulo(titulo)
        self.assertEqual(resultado.status, "ABERTO")
        self.assertEqual(atualizado["valor_original"], 100.0)
        self.assertEqual(atualizado["valor_pago"], 0.0)
        self.assertEqual(atualizado["saldo_aberto"], 100.0)

    def test_editar_recorrencia_preserva_estado_ativo(self):
        self.service.criar_recorrencia(identificador="NET", tipo="PAGAR", valor=99, dia_vencimento=10)
        self.service.ativar_recorrencia("NET", False)
        self.service.editar_recorrencia(
            "NET", tipo="PAGAR", valor=120, dia_vencimento=15,
            descricao="Internet", pessoa_nome="Operadora",
        )
        regra = self.service.listar_recorrencias()[0]
        self.assertEqual(regra["valor"], 120.0)
        self.assertEqual(regra["dia_vencimento"], 15)
        self.assertEqual(regra["descricao"], "Internet")
        self.assertEqual(regra["pessoa_nome"], "Operadora")
        self.assertFalse(regra["ativo"])

    def test_relatorio_centros_custo(self):
        pagar = self.service.criar_titulo(tipo="PAGAR", valor=80, data_vencimento="2026-08-10", data_emissao="2026-08-01")
        receber = self.service.criar_titulo(tipo="RECEBER", valor=150, data_vencimento="2026-08-10", data_emissao="2026-08-01")
        self.service.definir_centro_custo(pagar, "Operacional")
        self.service.definir_centro_custo(receber, "Operacional")
        relatorio = self.service.relatorio_centros_custo("2026-08-01", "2026-08-31")
        self.assertEqual(relatorio[0]["pagar"], 80.0)
        self.assertEqual(relatorio[0]["receber"], 150.0)
        self.assertEqual(relatorio[0]["saldo"], 70.0)

    def test_fluxo_caixa_inclui_venda_e_despesa_legadas_pagas(self):
        with self.database.session(write=True) as conn:
            conn.execute(
                "INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento,forma_pagamento) VALUES('COMPRA','Venda balcão',120,'2026-08-12 10:00:00','PAGO','PIX')"
            )
            conn.execute(
                "INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento,forma_pagamento) VALUES('DESPESA','Frete',20,'2026-08-12 11:00:00','PAGO','DINHEIRO')"
            )
            conn.execute(
                "INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento) VALUES('COMPRA','Venda crediário',50,'2026-08-12 12:00:00','PENDENTE')"
            )
        fluxo = self.service.fluxo_caixa('2026-08-01', '2026-08-31')
        self.assertEqual(fluxo['entradas'], 120.0)
        self.assertEqual(fluxo['saidas'], 20.0)
        self.assertEqual(fluxo['saldo'], 100.0)
        self.assertEqual({m['fonte'] for m in fluxo['movimentos']}, {'MOVIMENTACAO'})

    def test_dre_inclui_movimentacao_legada_sem_duplicar_origem_financeiro(self):
        with self.database.session(write=True) as conn:
            conn.execute(
                "INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento) VALUES('COMPRA','Venda paga',100,'2026-08-03','PAGO')"
            )
            conn.execute(
                "INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento) VALUES('COMPRA','Venda em aberto',60,'2026-08-04','PENDENTE')"
            )
            conn.execute(
                "INSERT INTO movimentacoes(tipo,descricao,valor,data,status_pagamento,origem_sistema) VALUES('COMPRA','Espelho financeiro',999,'2026-08-05','PAGO','FINANCEIRO')"
            )
        dre = self.service.dre('2026-08-01', '2026-08-31')
        self.assertEqual(dre['receitas_competencia'], 160.0)
        self.assertEqual(dre['receitas_realizadas'], 100.0)
        self.assertEqual(dre['resultado_competencia'], 160.0)
        self.assertEqual(dre['resultado_realizado'], 100.0)


if __name__ == "__main__":
    unittest.main()

class FinanceiroAuditoriaAdicionalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "financeiro_auditoria.db")
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA)
        conn.close()
        self.database = DatabaseManager(self.db_path)
        self.repo = FinanceiroRepository(self.database)
        self.service = FinanceiroService(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejeita_forma_pagamento_invalida(self):
        titulo = self.service.criar_titulo(tipo="RECEBER", valor=50, data_vencimento="2026-08-20")
        with self.assertRaisesRegex(ValueError, "Forma de pagamento inválida"):
            self.service.pagar(titulo, 50, forma_pagamento="CHEQUE_FANTASMA")

    def test_normaliza_forma_pagamento(self):
        titulo = self.service.criar_titulo(tipo="RECEBER", valor=50, data_vencimento="2026-08-20")
        resultado = self.service.pagar(titulo, 50, forma_pagamento=" pix ")
        pagamento = self.repo.obter_pagamento(resultado.pagamento_id)
        self.assertEqual(pagamento["forma_pagamento"], "PIX")

    def test_operacoes_recorrencia_e_conciliacao_geram_auditoria(self):
        self.service.criar_recorrencia(
            identificador="ENERGIA", tipo="PAGAR", valor=200, dia_vencimento=10,
            usuario="maria",
        )
        self.service.editar_recorrencia(
            "ENERGIA", tipo="PAGAR", valor=220, dia_vencimento=12,
            usuario="maria",
        )
        self.service.ativar_recorrencia("ENERGIA", False, usuario="maria")
        titulo = self.service.criar_titulo(tipo="PAGAR", valor=20, data_vencimento="2026-08-20")
        pagamento = self.service.pagar(titulo, 20, forma_pagamento="PIX", usuario="maria")
        self.service.conciliar_pagamento(pagamento.pagamento_id, "EXTRATO-XYZ", usuario="maria")
        self.service.desfazer_conciliacao(pagamento.pagamento_id, usuario="maria")
        self.service.excluir_recorrencia("ENERGIA", usuario="maria")
        acoes = {
            row["acao"] for row in self.database.fetch_all(
                "SELECT acao FROM auditoria WHERE usuario='maria' AND modulo='Financeiro'"
            )
        }
        self.assertTrue({
            "CRIAR_RECORRENCIA", "EDITAR_RECORRENCIA", "ATIVAR_RECORRENCIA",
            "CONCILIAR_PAGAMENTO", "DESFAZER_CONCILIACAO", "EXCLUIR_RECORRENCIA",
        }.issubset(acoes))

class FinanceiroIntegracaoVendaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "financeiro_venda.db")
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA)
        conn.close()
        self.database = DatabaseManager(self.db_path)
        self.repo = FinanceiroRepository(self.database)
        self.service = FinanceiroService(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_venda_crediario_cria_titulo_na_mesma_transacao(self):
        with self.database.session(write=True) as conn:
            titulo_id = self.service.registrar_venda_crediario_transacao(
                conn, venda_id=15, cliente_id=7, cliente_nome="CLIENTE TESTE",
                valor=120, data_vencimento="2026-09-01", usuario="caixa",
            )
        titulo = self.repo.obter_titulo(titulo_id)
        self.assertEqual(titulo["tipo"], "RECEBER")
        self.assertEqual(titulo["origem"], "VENDA")
        self.assertEqual(titulo["origem_id"], "15")
        self.assertEqual(titulo["pessoa_id"], 7)
        self.assertEqual(titulo["valor_original"], 120.0)

    def test_cancelamento_da_venda_cancela_titulo_sem_pagamento(self):
        with self.database.session(write=True) as conn:
            titulo_id = self.service.registrar_venda_crediario_transacao(
                conn, venda_id=16, cliente_id=8, cliente_nome="CLIENTE",
                valor=80, data_vencimento="2026-09-01",
            )
            ids = self.service.cancelar_titulos_origem_transacao(
                conn, tipo="RECEBER", origem="VENDA", origem_id=16, usuario="gerente"
            )
        self.assertEqual(ids, [titulo_id])
        self.assertEqual(self.repo.obter_titulo(titulo_id)["status"], "CANCELADO")

    def test_cancelamento_da_venda_bloqueia_titulo_com_pagamento(self):
        titulo_id = self.service.criar_titulo(
            tipo="RECEBER", valor=50, data_vencimento="2026-09-01",
            origem="VENDA", origem_id="17", documento="VENDA-17",
        )
        self.service.pagar(titulo_id, 10, forma_pagamento="PIX")
        with self.database.session(write=True) as conn:
            with self.assertRaisesRegex(ValueError, "possui pagamento"):
                self.service.cancelar_titulos_origem_transacao(
                    conn, tipo="RECEBER", origem="VENDA", origem_id=17
                )

class FinanceiroIntegracaoCobrancaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "financeiro_cobranca.db")
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA + """
        CREATE TABLE clientes (
          id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, saldo_devedor REAL DEFAULT 0
        );
        CREATE TABLE parcelas (
          id INTEGER PRIMARY KEY AUTOINCREMENT, movimentacao_id INTEGER,
          numero_parcela INTEGER, valor_parcela REAL, vencimento TEXT,
          status TEXT DEFAULT 'PENDENTE', valor_pago REAL DEFAULT 0,
          data_pagamento TEXT DEFAULT '', atraso_registrado INTEGER DEFAULT 0
        );
        """)
        conn.close()
        self.database = DatabaseManager(self.db_path)
        self.repo = FinanceiroRepository(self.database)
        self.service = FinanceiroService(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def _venda(self, valor=100.0):
        with self.database.session(write=True) as conn:
            cliente_id = conn.execute(
                "INSERT INTO clientes(nome,saldo_devedor) VALUES('CLIENTE',?)", (valor,)
            ).lastrowid
            venda_id = conn.execute(
                "INSERT INTO movimentacoes(cliente_id,tipo,valor,status_pagamento,valor_aberto) "
                "VALUES(?, 'COMPRA', ?, 'PENDENTE', ?)",
                (cliente_id, valor, valor),
            ).lastrowid
            parcela_id = conn.execute(
                "INSERT INTO parcelas(movimentacao_id,numero_parcela,valor_parcela,vencimento,status) "
                "VALUES(?,1,?,'2026-08-01','PENDENTE')",
                (venda_id, valor),
            ).lastrowid
            titulo_id = self.service.registrar_venda_crediario_transacao(
                conn, venda_id=venda_id, cliente_id=cliente_id, cliente_nome='CLIENTE',
                valor=valor, data_vencimento='2026-08-01', usuario='caixa',
            )
        return cliente_id, venda_id, parcela_id, titulo_id


    def test_cancelamento_isolado_de_titulo_de_venda_e_bloqueado(self):
        _cliente_id, _venda_id, _parcela_id, titulo_id = self._venda()
        with self.assertRaisesRegex(ValueError, "módulo de origem"):
            self.service.cancelar(titulo_id, usuario="gerente")
        titulo = self.repo.obter_titulo(titulo_id)
        self.assertEqual(titulo["status"], "ABERTO")

    def test_baixa_financeira_sincroniza_cobranca_legada(self):
        cliente_id, venda_id, parcela_id, titulo_id = self._venda()
        resultado = self.service.pagar(
            titulo_id, 40, forma_pagamento='PIX', data_pagamento='2026-08-10'
        )
        with self.database.session() as conn:
            movimento = conn.execute(
                "SELECT valor_aberto,status_pagamento FROM movimentacoes WHERE id=?", (venda_id,)
            ).fetchone()
            parcela = conn.execute(
                "SELECT valor_pago,status FROM parcelas WHERE id=?", (parcela_id,)
            ).fetchone()
            cliente = conn.execute(
                "SELECT saldo_devedor FROM clientes WHERE id=?", (cliente_id,)
            ).fetchone()
        self.assertEqual(resultado.status, 'PARCIAL')
        self.assertEqual(float(movimento['valor_aberto']), 60.0)
        self.assertEqual(movimento['status_pagamento'], 'PARCIAL')
        self.assertEqual(float(parcela['valor_pago']), 40.0)
        self.assertEqual(parcela['status'], 'PARCIAL')
        self.assertEqual(float(cliente['saldo_devedor']), 60.0)

    def test_estorno_restaura_venda_parcela_e_saldo_cliente(self):
        cliente_id, venda_id, parcela_id, titulo_id = self._venda()
        pagamento = self.service.pagar(
            titulo_id, 100, forma_pagamento='DINHEIRO', data_pagamento='2026-08-10'
        )
        self.service.estornar_pagamento(pagamento.pagamento_id, usuario='gerente')
        with self.database.session() as conn:
            movimento = conn.execute(
                "SELECT valor_aberto,status_pagamento FROM movimentacoes WHERE id=?", (venda_id,)
            ).fetchone()
            parcela = conn.execute(
                "SELECT valor_pago,status,data_pagamento,atraso_registrado FROM parcelas WHERE id=?", (parcela_id,)
            ).fetchone()
            cliente = conn.execute(
                "SELECT saldo_devedor FROM clientes WHERE id=?", (cliente_id,)
            ).fetchone()
        self.assertEqual(float(movimento['valor_aberto']), 100.0)
        self.assertEqual(movimento['status_pagamento'], 'PENDENTE')
        self.assertEqual(float(parcela['valor_pago']), 0.0)
        self.assertEqual(parcela['status'], 'PENDENTE')
        self.assertEqual(parcela['data_pagamento'], '')
        self.assertEqual(int(parcela['atraso_registrado']), 0)
        self.assertEqual(float(cliente['saldo_devedor']), 100.0)


    def test_baixa_com_encargos_sincroniza_apenas_principal_no_legado(self):
        cliente_id, venda_id, parcela_id, titulo_id = self._venda()
        resultado = self.service.baixar_com_encargos(
            titulo_id, multa_percentual=10, juros_mensal_percentual=0,
            data_pagamento='2026-08-10', forma_pagamento='PIX', usuario='caixa',
        )
        with self.database.session() as conn:
            movimento = conn.execute(
                "SELECT valor_aberto,status_pagamento FROM movimentacoes WHERE id=?", (venda_id,)
            ).fetchone()
            parcela = conn.execute(
                "SELECT valor_pago,status FROM parcelas WHERE id=?", (parcela_id,)
            ).fetchone()
            cliente = conn.execute(
                "SELECT saldo_devedor FROM clientes WHERE id=?", (cliente_id,)
            ).fetchone()
            titulo = conn.execute(
                "SELECT valor_original,valor_pago,status FROM titulos_financeiros WHERE id=?", (titulo_id,)
            ).fetchone()
        self.assertEqual(resultado.status, 'PAGO')
        self.assertEqual(float(titulo['valor_original']), 110.0)
        self.assertEqual(float(titulo['valor_pago']), 110.0)
        self.assertEqual(float(movimento['valor_aberto']), 0.0)
        self.assertEqual(movimento['status_pagamento'], 'PAGO')
        self.assertEqual(float(parcela['valor_pago']), 100.0)
        self.assertEqual(parcela['status'], 'PAGO')
        self.assertEqual(float(cliente['saldo_devedor']), 0.0)

    def test_estorno_baixa_com_encargos_restaura_principal_legado_e_remove_encargos(self):
        cliente_id, venda_id, parcela_id, titulo_id = self._venda()
        pagamento = self.service.baixar_com_encargos(
            titulo_id, multa_percentual=10, juros_mensal_percentual=0,
            data_pagamento='2026-08-10', forma_pagamento='DINHEIRO', usuario='caixa',
        )
        self.service.estornar_pagamento(pagamento.pagamento_id, usuario='gerente')
        with self.database.session() as conn:
            movimento = conn.execute(
                "SELECT valor_aberto,status_pagamento FROM movimentacoes WHERE id=?", (venda_id,)
            ).fetchone()
            parcela = conn.execute(
                "SELECT valor_pago,status FROM parcelas WHERE id=?", (parcela_id,)
            ).fetchone()
            cliente = conn.execute(
                "SELECT saldo_devedor FROM clientes WHERE id=?", (cliente_id,)
            ).fetchone()
            titulo = conn.execute(
                "SELECT valor_original,valor_pago,status FROM titulos_financeiros WHERE id=?", (titulo_id,)
            ).fetchone()
        self.assertEqual(float(titulo['valor_original']), 100.0)
        self.assertEqual(float(titulo['valor_pago']), 0.0)
        self.assertEqual(titulo['status'], 'ABERTO')
        self.assertEqual(float(movimento['valor_aberto']), 100.0)
        self.assertEqual(movimento['status_pagamento'], 'PENDENTE')
        self.assertEqual(float(parcela['valor_pago']), 0.0)
        self.assertEqual(parcela['status'], 'PENDENTE')
        self.assertEqual(float(cliente['saldo_devedor']), 100.0)


    def test_recebimento_cobranca_atualiza_titulo_sem_dupla_baixa_legada(self):
        cliente_id, venda_id, parcela_id, titulo_id = self._venda()
        with self.database.session(write=True) as conn:
            resultado = self.service.registrar_recebimento_venda_transacao(
                conn, venda_id=venda_id, valor=40, forma_pagamento='PIX',
                observacao='Recebido na cobrança', usuario='maria', data_pagamento='2026-08-10',
            )
            movimento = conn.execute(
                "SELECT valor_aberto FROM movimentacoes WHERE id=?", (venda_id,)
            ).fetchone()
            parcela = conn.execute(
                "SELECT valor_pago FROM parcelas WHERE id=?", (parcela_id,)
            ).fetchone()
            cliente = conn.execute(
                "SELECT saldo_devedor FROM clientes WHERE id=?", (cliente_id,)
            ).fetchone()
        titulo = self.repo.obter_titulo(titulo_id)
        self.assertEqual(resultado.status, 'PARCIAL')
        self.assertEqual(float(titulo['valor_pago']), 40.0)
        self.assertEqual(float(titulo['saldo_aberto']), 60.0)
        self.assertEqual(float(movimento['valor_aberto']), 100.0)
        self.assertEqual(float(parcela['valor_pago']), 0.0)
        self.assertEqual(float(cliente['saldo_devedor']), 100.0)

    def test_relatorios_nao_duplicam_venda_com_titulo_financeiro(self):
        _cliente_id, venda_id, _parcela_id, titulo_id = self._venda()
        with self.database.session(write=True) as conn:
            conn.execute(
                "UPDATE movimentacoes SET data='2026-08-03', status_pagamento='PAGO', valor_aberto=0 WHERE id=?",
                (venda_id,),
            )
            conn.execute(
                "UPDATE titulos_financeiros SET data_emissao='2026-08-03', valor_pago=valor_original, status='PAGO' WHERE id=?",
                (titulo_id,),
            )
            self.service.registrar_recebimento_venda_transacao(
                conn, venda_id=venda_id, valor=0.01, forma_pagamento='PIX'
            ) if False else None
            conn.execute(
                "INSERT INTO pagamentos_titulos(titulo_id,valor,forma_pagamento,observacao,usuario,data_pagamento) VALUES(?,?,?,?,?,?)",
                (titulo_id,100,'PIX','','teste','2026-08-03'),
            )
        fluxo = self.service.fluxo_caixa('2026-08-01','2026-08-31')
        dre = self.service.dre('2026-08-01','2026-08-31')
        self.assertEqual(fluxo['entradas'], 100.0)
        self.assertEqual(dre['receitas_competencia'], 100.0)
        self.assertEqual(dre['receitas_realizadas'], 100.0)

    def test_estorno_antigo_exige_ordem_inversa(self):
        _cliente_id, _venda_id, _parcela_id, titulo_id = self._venda()
        primeiro = self.service.pagar(titulo_id, 30, forma_pagamento='PIX')
        self.service.pagar(titulo_id, 20, forma_pagamento='DINHEIRO')
        with self.assertRaisesRegex(ValueError, 'mais recentes'):
            self.service.estornar_pagamento(primeiro.pagamento_id)
