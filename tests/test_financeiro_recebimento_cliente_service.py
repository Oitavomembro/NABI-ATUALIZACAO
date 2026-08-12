from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile

from database import DatabaseManager
from repositories.financeiro_repository import FinanceiroRepository
from services.financeiro_service import FinanceiroService


def _schema(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE clientes(id INTEGER PRIMARY KEY,nome TEXT,saldo_devedor REAL);
    CREATE TABLE movimentacoes(
      id INTEGER PRIMARY KEY,cliente_id INTEGER,tipo TEXT,descricao TEXT,valor REAL,
      data TEXT,vencimento TEXT,status_pagamento TEXT,valor_aberto REAL,forma_pagamento TEXT
    );
    CREATE TABLE parcelas(
      id INTEGER PRIMARY KEY,movimentacao_id INTEGER,numero_parcela INTEGER,
      valor_parcela REAL,vencimento TEXT,status TEXT,valor_pago REAL,
      data_pagamento TEXT,atraso_registrado INTEGER DEFAULT 0,dados_confiaveis INTEGER DEFAULT 1
    );
    CREATE TABLE titulos_financeiros(
      id INTEGER PRIMARY KEY,tipo TEXT,origem TEXT,origem_id TEXT,documento TEXT,
      valor_original REAL,valor_pago REAL,status TEXT,atualizado_em TEXT
    );
    CREATE TABLE pagamentos_titulos(
      id INTEGER PRIMARY KEY,titulo_id INTEGER,valor REAL,forma_pagamento TEXT,
      observacao TEXT,usuario TEXT,data_pagamento TEXT
    );
    CREATE TABLE auditoria(data TEXT,usuario TEXT,modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
    INSERT INTO clientes VALUES(1,'Cliente',150.00);
    INSERT INTO movimentacoes VALUES(10,1,'COMPRA','Compra',300,'01/08/2026','01/09/2026','PARCIAL',150,'');
    INSERT INTO parcelas VALUES
      (1,10,1,100,'2026-07-01','PAGO',100,'2026-07-01',0,1),
      (2,10,2,100,'2026-08-01','PENDENTE',0,'',0,1),
      (3,10,3,100,'2026-09-01','PENDENTE',0,'',0,1);
    INSERT INTO titulos_financeiros VALUES(1,'RECEBER','VENDA','10','',300,150,'PARCIAL','');
    """)
    conn.commit()
    conn.close()


def test_recebimento_cliente_centraliza_transacao_e_decimal():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        _schema(path)
        manager = DatabaseManager(path)
        service = FinanceiroService(FinanceiroRepository(manager))

        preparado = service.preparar_recebimento_cliente(1)
        assert preparado["saldo"] == Decimal("150.00")
        assert list(preparado["alvos"]) == ["Saldo total do cliente"]
        resultado = service.receber_pagamento_cliente(
            cliente_id=1, valor="50,00".replace(",", "."), alvo={"tipo": "AUTO"},
            forma_pagamento="PIX", data_pagamento="2026-08-06",
        )
        assert resultado["valor"] == Decimal("50.00")
        assert resultado["novo_saldo"] == Decimal("100.00")

        conn = sqlite3.connect(path)
        assert conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0] == 100
        assert conn.execute("SELECT valor_aberto FROM movimentacoes WHERE id=10").fetchone()[0] == 100
        assert conn.execute("SELECT valor_pago,status FROM parcelas WHERE id=2").fetchone() == (100, "PAGO")
        assert conn.execute("SELECT COUNT(*) FROM movimentacoes WHERE tipo='PAGAMENTO'").fetchone()[0] == 1
        conn.close()


def test_pagamento_excedente_gera_rollback_integral():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        _schema(path)
        manager = DatabaseManager(path)
        service = FinanceiroService(FinanceiroRepository(manager))
        try:
            service.receber_pagamento_cliente(
                cliente_id=1, valor="200.00", alvo={"tipo": "AUTO", "limite": Decimal("150.00")},
                forma_pagamento="PIX", data_pagamento="2026-08-06",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Pagamento excedente deveria falhar")

        conn = sqlite3.connect(path)
        assert conn.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0] == 150
        assert conn.execute("SELECT COUNT(*) FROM movimentacoes WHERE tipo='PAGAMENTO'").fetchone()[0] == 0
        conn.close()
