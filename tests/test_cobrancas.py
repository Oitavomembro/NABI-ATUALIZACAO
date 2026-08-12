import sqlite3
import unittest
from datetime import date, timedelta


class CobrancasTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript("""
        CREATE TABLE clientes(id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT);
        CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, cliente_id INTEGER);
        CREATE TABLE parcelas(id INTEGER PRIMARY KEY, movimentacao_id INTEGER, numero_parcela INTEGER,
            valor_parcela REAL, valor_pago REAL DEFAULT 0, vencimento TEXT, status TEXT DEFAULT 'PENDENTE', dados_confiaveis INTEGER DEFAULT 1);
        CREATE TABLE lembretes_promissorias(id INTEGER PRIMARY KEY, cliente_id INTEGER, parcela_id INTEGER UNIQUE,
            dias_antecedencia INTEGER, observacao TEXT, ativo INTEGER DEFAULT 1, criado_em TEXT, ultimo_aviso_em TEXT DEFAULT '');
        CREATE TABLE contatos_cobranca(id INTEGER PRIMARY KEY, cliente_id INTEGER, parcela_id INTEGER,
            tipo TEXT, resultado TEXT, observacao TEXT, proximo_contato TEXT, data TEXT);
        """)
        self.conn.execute("INSERT INTO clientes VALUES(1,'João','11999999999')")
        self.conn.execute("INSERT INTO movimentacoes VALUES(1,1)")

    def tearDown(self):
        self.conn.close()

    def test_parcela_atrasada_e_detectada(self):
        venc = (date.today() - timedelta(days=3)).isoformat()
        self.conn.execute("INSERT INTO parcelas VALUES(1,1,1,100,20,?,'PARCIAL',1)", (venc,))
        row = self.conn.execute("""
            SELECT MAX(0,COALESCE(valor_parcela,0)-COALESCE(valor_pago,0))
            FROM parcelas WHERE status<>'PAGO' AND date(vencimento)<date('now','localtime')
        """).fetchone()
        self.assertEqual(row[0], 80)

    def test_lembrete_aparece_na_antecedencia(self):
        venc = (date.today() + timedelta(days=2)).isoformat()
        self.conn.execute("INSERT INTO parcelas VALUES(2,1,2,150,0,?,'PENDENTE',1)", (venc,))
        self.conn.execute("INSERT INTO lembretes_promissorias(cliente_id,parcela_id,dias_antecedencia,observacao,criado_em) VALUES(1,2,3,'Avisar pelo WhatsApp','agora')")
        qtd = self.conn.execute("""
            SELECT COUNT(*) FROM lembretes_promissorias l JOIN parcelas p ON p.id=l.parcela_id
            WHERE l.ativo=1 AND p.status<>'PAGO'
              AND date('now','localtime') >= date(p.vencimento, '-' || l.dias_antecedencia || ' day')
              AND date('now','localtime') <= date(p.vencimento)
        """).fetchone()[0]
        self.assertEqual(qtd, 1)

    def test_lembrete_nao_aparece_muito_cedo(self):
        venc = (date.today() + timedelta(days=10)).isoformat()
        self.conn.execute("INSERT INTO parcelas VALUES(3,1,3,200,0,?,'PENDENTE',1)", (venc,))
        self.conn.execute("INSERT INTO lembretes_promissorias(cliente_id,parcela_id,dias_antecedencia,observacao,criado_em) VALUES(1,3,2,'Avisar','agora')")
        qtd = self.conn.execute("""
            SELECT COUNT(*) FROM lembretes_promissorias l JOIN parcelas p ON p.id=l.parcela_id
            WHERE date('now','localtime') >= date(p.vencimento, '-' || l.dias_antecedencia || ' day')
        """).fetchone()[0]
        self.assertEqual(qtd, 0)


if __name__ == '__main__':
    unittest.main()
