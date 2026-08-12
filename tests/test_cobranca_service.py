import sqlite3
import tempfile
import unittest
from datetime import date, timedelta, datetime
from pathlib import Path

from database import DatabaseManager
from services import CobrancaService


class CobrancaServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "cobrancas.db"
        conn = sqlite3.connect(self.path)
        conn.executescript("""
        CREATE TABLE clientes(id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT);
        CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, cliente_id INTEGER);
        CREATE TABLE parcelas(id INTEGER PRIMARY KEY, movimentacao_id INTEGER, numero_parcela INTEGER,
            valor_parcela REAL, valor_pago REAL DEFAULT 0, vencimento TEXT, status TEXT DEFAULT 'PENDENTE', dados_confiaveis INTEGER DEFAULT 1);
        CREATE TABLE lembretes_promissorias(id INTEGER PRIMARY KEY, cliente_id INTEGER, parcela_id INTEGER UNIQUE,
            dias_antecedencia INTEGER, observacao TEXT, ativo INTEGER DEFAULT 1, criado_em TEXT, ultimo_aviso_em TEXT DEFAULT '');
        CREATE TABLE contatos_cobranca(id INTEGER PRIMARY KEY, cliente_id INTEGER, parcela_id INTEGER,
            tipo TEXT, resultado TEXT, observacao TEXT, proximo_contato TEXT, data TEXT);
        INSERT INTO clientes VALUES(1,'João','11999999999');
        INSERT INTO movimentacoes VALUES(1,1);
        """)
        conn.close()
        self.service = CobrancaService(DatabaseManager(self.path))

    def tearDown(self):
        self.temp.cleanup()

    def _parcela(self, pid=1, dias=-3, valor=100):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO parcelas VALUES(?,?,?,?,?,?,?,?)", (
            pid, 1, pid, valor, 0, (date.today()+timedelta(days=dias)).isoformat(), 'PENDENTE', 1
        ))
        conn.commit(); conn.close()

    def test_filtra_sem_contato_e_retorno_vencido(self):
        self._parcela()
        self.assertEqual(len(self.service.listar_atrasadas('Sem contato')), 1)
        self.service.registrar_contato(cliente_id=1, parcela_id=1, tipo='COBRANCA', resultado='Prometeu pagar', proximo_contato=date.today().isoformat())
        self.assertEqual(len(self.service.listar_atrasadas('Sem contato')), 0)
        self.assertEqual(len(self.service.listar_atrasadas('Prometeu pagar')), 1)
        self.assertEqual(len(self.service.listar_atrasadas('Retorno vencido')), 1)

    def test_lista_retorno_mais_recente_por_parcela(self):
        self._parcela()
        ontem=(date.today()-timedelta(days=1)).isoformat()
        self.service.registrar_contato(cliente_id=1, parcela_id=1, tipo='COBRANCA', resultado='Não respondeu', proximo_contato=ontem)
        self.service.registrar_contato(cliente_id=1, parcela_id=1, tipo='COBRANCA', resultado='Negociando', proximo_contato=date.today().isoformat())
        rows=self.service.listar_retornos_pendentes()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['resultado'],'Negociando')

    def test_lembrete_nao_repete_no_mesmo_dia(self):
        self._parcela(pid=2,dias=2,valor=150)
        agora=datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        conn=sqlite3.connect(self.path)
        conn.execute("INSERT INTO lembretes_promissorias VALUES(1,1,2,3,'Avisar',1,'agora',?)",(agora,))
        conn.commit(); conn.close()
        self.assertEqual(self.service.listar_lembretes_para_hoje(),[])

    def test_dados_parcela_e_parcelas_pendentes(self):
        self._parcela(pid=3, dias=5, valor=240)
        dados = self.service.dados_parcela(3)
        self.assertEqual(dados["cliente_id"], 1)
        self.assertEqual(dados["nome"], "João")
        self.assertEqual(float(dados["valor_aberto"]), 240.0)
        pendentes = self.service.parcelas_pendentes_cliente(1)
        self.assertEqual([row["parcela_id"] for row in pendentes], [3])

    def test_salvar_e_marcar_lembrete_enviado(self):
        self._parcela(pid=4, dias=2, valor=80)
        self.service.salvar_lembrete(cliente_id=1, parcela_id=4, dias_antecedencia=2, observacao="Avisar")
        conn = sqlite3.connect(self.path)
        lembrete_id = conn.execute("SELECT id FROM lembretes_promissorias WHERE parcela_id=4").fetchone()[0]
        conn.close()
        dados = self.service.dados_lembrete(lembrete_id)
        self.assertEqual(dados["observacao"], "Avisar")
        self.service.marcar_lembrete_enviado(lembrete_id=lembrete_id, cliente_id=1, parcela_id=4, observacao="Avisar")
        conn = sqlite3.connect(self.path)
        ultimo, contatos = conn.execute("SELECT ultimo_aviso_em FROM lembretes_promissorias WHERE id=?", (lembrete_id,)).fetchone()[0], conn.execute("SELECT COUNT(*) FROM contatos_cobranca WHERE parcela_id=4 AND tipo='LEMBRETE'").fetchone()[0]
        conn.close()
        self.assertTrue(ultimo)
        self.assertEqual(contatos, 1)

    def test_dados_retorno(self):
        self._parcela(pid=5, dias=-2, valor=120)
        contato_id = self.service.registrar_contato(cliente_id=1, parcela_id=5, tipo="RETORNO", resultado="Negociando", proximo_contato=date.today().isoformat())
        dados = self.service.dados_retorno(contato_id)
        self.assertEqual(dados["parcela_id"], 5)
        self.assertEqual(dados["nome"], "João")
        self.assertEqual(float(dados["valor_aberto"]), 120.0)

    def test_mensagens_contem_dados(self):
        texto=self.service.mensagem_cobranca(nome='João',loja='Loja X',parcela=2,valor=99.5,vencimento='2026-08-01')
        self.assertIn('João',texto)
        self.assertIn('R$ 99.50',texto)
        self.assertIn('Loja X',texto)


if __name__ == '__main__':
    unittest.main()

class CobrancaDecimalPrecisionTests(unittest.TestCase):
    def test_resumo_preserva_decimal_sem_float(self):
        from decimal import Decimal
        service = object.__new__(CobrancaService)
        resumo = service.resumo([
            {"valor_aberto": "0.1000000000000000001"},
            {"valor_aberto": "0.2000000000000000002"},
        ])
        self.assertEqual(resumo.total, Decimal("0.3000000000000000003"))

    def test_mensagem_formata_decimal_diretamente(self):
        from decimal import Decimal
        texto = CobrancaService.mensagem_cobranca(
            nome="Ana", loja="Loja", parcela=1,
            valor=Decimal("99.50"), vencimento="2026-08-10",
        )
        self.assertIn("R$ 99.50", texto)
