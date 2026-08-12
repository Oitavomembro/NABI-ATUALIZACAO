from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile

from database import DatabaseManager
from repositories.financeiro_repository import FinanceiroRepository
from services.financeiro_service import FinanceiroService
from services.receipt_service import ReceiptService


def _schema(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE clientes(id INTEGER PRIMARY KEY,nome TEXT,codigo TEXT DEFAULT '',numero_ficha TEXT DEFAULT '',telefone TEXT DEFAULT '',endereco TEXT DEFAULT '',saldo_devedor REAL,saldo_devedor_decimal TEXT);
    CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,cliente_id INTEGER,tipo TEXT,descricao TEXT,valor REAL,data TEXT,vencimento TEXT,status_pagamento TEXT,valor_aberto REAL,valor_aberto_decimal TEXT,forma_pagamento TEXT,responsavel TEXT DEFAULT '',total_parcelas INTEGER DEFAULT 1);
    CREATE TABLE parcelas(id INTEGER PRIMARY KEY AUTOINCREMENT,movimentacao_id INTEGER,numero_parcela INTEGER,valor_parcela REAL,valor_parcela_decimal TEXT,vencimento TEXT,status TEXT,valor_pago REAL,valor_pago_decimal TEXT,data_pagamento TEXT DEFAULT '',atraso_registrado INTEGER DEFAULT 0,dados_confiaveis INTEGER DEFAULT 1);
    CREATE TABLE titulos_financeiros(id INTEGER PRIMARY KEY AUTOINCREMENT,tipo TEXT,origem TEXT,origem_id TEXT,documento TEXT,valor_original REAL,valor_original_decimal TEXT,valor_pago REAL,valor_pago_decimal TEXT,status TEXT,atualizado_em TEXT);
    CREATE TABLE pagamentos_titulos(id INTEGER PRIMARY KEY AUTOINCREMENT,titulo_id INTEGER,valor REAL,valor_decimal TEXT,forma_pagamento TEXT,observacao TEXT,usuario TEXT,data_pagamento TEXT);
    CREATE TABLE auditoria(data TEXT,usuario TEXT,modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
    CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT);
    """)
    conn.commit(); conn.close()


def _service(path):
    return FinanceiroService(FinanceiroRepository(DatabaseManager(path)))


def test_ficha_migrada_com_saldo_90_e_sem_compras_aceita_pagamento_20():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'db.sqlite'; _schema(path)
        conn = sqlite3.connect(path)
        conn.execute("INSERT INTO clientes(id,nome,codigo,numero_ficha,saldo_devedor,saldo_devedor_decimal) VALUES(1,'DEIDE','C2644','2644',90,'90.00')")
        conn.commit(); conn.close()

        preparado = _service(path).preparar_recebimento_cliente(1)
        assert preparado['saldo'] == Decimal('90.00')
        assert preparado['saldo_compras'] == Decimal('0.00')
        assert preparado['saldo_residual_legado'] == Decimal('90.00')
        assert list(preparado['alvos']) == ['Saldo total do cliente']

        resultado = _service(path).receber_pagamento_cliente(
            cliente_id=1, valor='20.00', alvo={'tipo':'PARCELA','mov_id':999,'parcela_id':999},
            forma_pagamento='DINHEIRO', data_pagamento='2026-08-07'
        )
        assert resultado['saldo_anterior'] == Decimal('90.00')
        assert resultado['novo_saldo'] == Decimal('70.00')
        assert resultado['alocacoes'][-1]['tipo'] == 'SALDO_LEGADO'
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT saldo_devedor_decimal FROM clientes WHERE id=1").fetchone()[0] == '70'
        assert conn.execute("SELECT COUNT(*) FROM movimentacoes WHERE tipo='PAGAMENTO'").fetchone()[0] == 1
        conn.close()


def test_saldo_600_com_compras_415_recebe_sobre_total_600():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'db.sqlite'; _schema(path)
        conn = sqlite3.connect(path)
        conn.execute("INSERT INTO clientes(id,nome,codigo,numero_ficha,saldo_devedor,saldo_devedor_decimal) VALUES(1,'Cliente','C','1',600,'600.00')")
        conn.execute("INSERT INTO movimentacoes(id,cliente_id,tipo,descricao,valor,data,vencimento,status_pagamento,valor_aberto,valor_aberto_decimal,forma_pagamento,total_parcelas) VALUES(10,1,'COMPRA','Antiga',415,'01/01/2026','01/02/2026','PARCIAL',415,'415.00','CREDIARIO',1)")
        conn.commit(); conn.close()

        preparado = _service(path).preparar_recebimento_cliente(1)
        assert preparado['saldo'] == Decimal('600.00')
        assert preparado['saldo_compras'] == Decimal('415.00')
        assert preparado['saldo_residual_legado'] == Decimal('185.00')
        resultado = _service(path).receber_pagamento_cliente(
            cliente_id=1, valor='500', alvo=None, forma_pagamento='PIX', data_pagamento='2026-08-07'
        )
        assert resultado['novo_saldo'] == Decimal('100.00')
        assert sum(a['valor_aplicado'] for a in resultado['alocacoes']) == Decimal('500.00')
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT saldo_devedor_decimal FROM clientes WHERE id=1").fetchone()[0] == '100'
        assert conn.execute("SELECT valor_aberto_decimal FROM movimentacoes WHERE id=10").fetchone()[0] == '0'
        conn.close()


def test_recibo_identifica_saldo_historico_migrado_sem_inventar_parcela():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'db.sqlite'; _schema(path)
        conn = sqlite3.connect(path)
        conn.execute("INSERT INTO clientes(id,nome,codigo,numero_ficha,saldo_devedor,saldo_devedor_decimal) VALUES(1,'Cliente','C','1',90,'90.00')")
        conn.commit(); conn.close()
        result = _service(path).receber_pagamento_cliente(cliente_id=1,valor='20',alvo=None,forma_pagamento='PIX',data_pagamento='2026-08-07')
        text = ReceiptService(DatabaseManager(path), config_getter=lambda _:'').build_payment_text(
            result['pagamento_mov_id'], result['alocacoes'], balance_before=result['saldo_anterior'], balance_after=result['novo_saldo']
        )
        assert 'Saldo antes: R$ 90.00' in text
        assert 'Saldo depois: R$ 70.00' in text
        assert 'Saldo histórico migrado' in text
