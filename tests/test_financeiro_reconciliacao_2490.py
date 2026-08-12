from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile

import pytest

from database import DatabaseManager
from repositories.financeiro_repository import FinanceiroRepository
from services.financeiro_service import FinanceiroService
from services.receipt_service import ReceiptService


def schema(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE clientes(
      id INTEGER PRIMARY KEY,nome TEXT,codigo TEXT DEFAULT '',numero_ficha TEXT DEFAULT '',
      telefone TEXT DEFAULT '',endereco TEXT DEFAULT '',saldo_devedor REAL,
      saldo_devedor_decimal TEXT
    );
    CREATE TABLE movimentacoes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,cliente_id INTEGER,tipo TEXT,descricao TEXT,valor REAL,
      data TEXT,vencimento TEXT,status_pagamento TEXT,valor_aberto REAL,valor_aberto_decimal TEXT,
      forma_pagamento TEXT,responsavel TEXT DEFAULT '',total_parcelas INTEGER DEFAULT 1
    );
    CREATE TABLE parcelas(
      id INTEGER PRIMARY KEY AUTOINCREMENT,movimentacao_id INTEGER,numero_parcela INTEGER,
      valor_parcela REAL,valor_parcela_decimal TEXT,vencimento TEXT,status TEXT,
      valor_pago REAL,valor_pago_decimal TEXT,data_pagamento TEXT DEFAULT '',
      atraso_registrado INTEGER DEFAULT 0,dados_confiaveis INTEGER DEFAULT 1
    );
    CREATE TABLE titulos_financeiros(
      id INTEGER PRIMARY KEY AUTOINCREMENT,tipo TEXT,origem TEXT,origem_id TEXT,documento TEXT,
      valor_original REAL,valor_original_decimal TEXT,valor_pago REAL,valor_pago_decimal TEXT,
      status TEXT,atualizado_em TEXT
    );
    CREATE TABLE pagamentos_titulos(
      id INTEGER PRIMARY KEY AUTOINCREMENT,titulo_id INTEGER,valor REAL,valor_decimal TEXT,
      forma_pagamento TEXT,observacao TEXT,usuario TEXT,data_pagamento TEXT
    );
    CREATE TABLE auditoria(data TEXT,usuario TEXT,modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
    CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT);
    """)
    conn.commit()
    conn.close()


def service_for(path: Path) -> FinanceiroService:
    return FinanceiroService(FinanceiroRepository(DatabaseManager(path)))


def add_customer(conn, customer_id: int, balance: str) -> None:
    conn.execute(
        "INSERT INTO clientes(id,nome,codigo,numero_ficha,saldo_devedor,saldo_devedor_decimal) VALUES(?,?,?,?,?,?)",
        (customer_id, "Cliente", "C1", "F1", float(balance), balance),
    )


def add_sale(conn, sale_id: int, customer_id: int, open_value: str, parcels: list[tuple[str, str]]) -> None:
    total = sum(Decimal(v) for v, _ in parcels)
    conn.execute(
        "INSERT INTO movimentacoes(id,cliente_id,tipo,descricao,valor,data,vencimento,status_pagamento,valor_aberto,valor_aberto_decimal,forma_pagamento,total_parcelas) "
        "VALUES(?,?,'COMPRA','Venda',?,'01/08/2026','01/09/2026','PARCIAL',?,?,'CREDIARIO',?)",
        (sale_id, customer_id, float(total), float(open_value), open_value, len(parcels)),
    )
    for number, (amount, paid) in enumerate(parcels, 1):
        amount_d, paid_d = Decimal(amount), Decimal(paid)
        status = "PAGO" if paid_d >= amount_d else ("PARCIAL" if paid_d else "PENDENTE")
        conn.execute(
            "INSERT INTO parcelas(movimentacao_id,numero_parcela,valor_parcela,valor_parcela_decimal,vencimento,status,valor_pago,valor_pago_decimal) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (sale_id, number, float(amount_d), str(amount_d), f"2026-0{min(number+7,9)}-01", status, float(paid_d), str(paid_d)),
        )
    paid_title = total - Decimal(open_value)
    conn.execute(
        "INSERT INTO titulos_financeiros(tipo,origem,origem_id,documento,valor_original,valor_original_decimal,valor_pago,valor_pago_decimal,status,atualizado_em) "
        "VALUES('RECEBER','VENDA',?,'',?,?,?,?,?,'')",
        (str(sale_id), float(total), str(total), float(paid_title), str(paid_title), "PARCIAL" if open_value != "0" else "PAGO"),
    )


def test_saldo_220_pagamento_20_e_aceito_e_reconciliado():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        schema(path)
        conn = sqlite3.connect(path)
        add_customer(conn, 1, "220.00")
        add_sale(conn, 10, 1, "220.00", [("110.00", "0.00"), ("110.00", "0.00")])
        conn.commit(); conn.close()

        result = service_for(path).receber_pagamento_cliente(
            cliente_id=1, valor="20.00", alvo={"tipo": "AUTO"}, forma_pagamento="PIX", data_pagamento="2026-08-07"
        )
        assert result["saldo_anterior"] == Decimal("220.00")
        assert result["novo_saldo"] == Decimal("200.00")
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT saldo_devedor_decimal FROM clientes WHERE id=1").fetchone()[0] == "200"
        assert conn.execute("SELECT valor_aberto_decimal FROM movimentacoes WHERE id=10").fetchone()[0] == "200"
        assert sum(Decimal(r[0]) - Decimal(r[1]) for r in conn.execute(
            "SELECT valor_parcela_decimal,valor_pago_decimal FROM parcelas WHERE movimentacao_id=10"
        )) == Decimal("200.00")
        conn.close()


def test_multiplas_compras_e_parcelas_distribuem_sem_divergencia():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"; schema(path)
        conn = sqlite3.connect(path); add_customer(conn, 1, "300.00")
        add_sale(conn, 10, 1, "120.00", [("60.00", "0"), ("60.00", "0")])
        add_sale(conn, 11, 1, "180.00", [("90.00", "0"), ("90.00", "0")])
        conn.commit(); conn.close()
        result = service_for(path).receber_pagamento_cliente(
            cliente_id=1, valor="200", alvo={"tipo": "AUTO"}, forma_pagamento="DINHEIRO", data_pagamento="2026-08-07"
        )
        assert result["novo_saldo"] == Decimal("100.00")
        assert sum(a["valor_aplicado"] for a in result["alocacoes"]) == Decimal("200.00")
        assert service_for(path).reconciliar_cliente(1)["saldo_real"] == Decimal("100.00")


def test_divergencia_historica_preserva_saldo_total_e_corrige_parcelas():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"; schema(path)
        conn = sqlite3.connect(path); add_customer(conn, 1, "220.00")
        add_sale(conn, 10, 1, "150.00", [("100.00", "100.00"), ("100.00", "0"), ("100.00", "0")])
        conn.commit(); conn.close()
        rec = service_for(path).reconciliar_cliente(1)
        assert rec["saldo_real"] == Decimal("220.00")
        assert rec["saldo_residual_legado"] == Decimal("70.00")
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT saldo_devedor_decimal FROM clientes WHERE id=1").fetchone()[0] == "220.00"
        assert conn.execute("SELECT valor_pago_decimal FROM parcelas WHERE movimentacao_id=10 AND numero_parcela=2").fetchone()[0] == "50"
        conn.close()


def test_parcelas_historicas_incompletas_nao_bloqueiam_pagamento_total():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"; schema(path)
        conn = sqlite3.connect(path); add_customer(conn, 1, "150.00")
        add_sale(conn, 10, 1, "150.00", [("100.00", "50.00")])  # parcela detalha só R$ 50 em aberto
        conn.commit(); conn.close()
        result = service_for(path).receber_pagamento_cliente(
            cliente_id=1, valor="20", alvo={"tipo": "AUTO"}, forma_pagamento="PIX", data_pagamento="2026-08-07"
        )
        assert result["novo_saldo"] == Decimal("130.00")
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT saldo_devedor_decimal FROM clientes WHERE id=1").fetchone()[0] == "130"
        assert conn.execute("SELECT valor_aberto_decimal FROM movimentacoes WHERE id=10").fetchone()[0] == "130"
        assert conn.execute("SELECT COUNT(*) FROM movimentacoes WHERE tipo='PAGAMENTO'").fetchone()[0] == 1
        conn.close()

def test_recibo_usa_saldo_reconciliado_persistido():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"; schema(path)
        conn = sqlite3.connect(path); add_customer(conn, 1, "220.00")
        add_sale(conn, 10, 1, "220.00", [("110.00", "0"), ("110.00", "0")])
        conn.commit(); conn.close()
        result = service_for(path).receber_pagamento_cliente(
            cliente_id=1, valor="20", alvo={"tipo": "AUTO"}, forma_pagamento="PIX", data_pagamento="2026-08-07"
        )
        receipt = ReceiptService(DatabaseManager(path), config_getter=lambda _key: "").build_payment_text(
            result["pagamento_mov_id"],
            result["alocacoes"],
            balance_before=result["saldo_anterior"],
            balance_after=result["novo_saldo"],
        )
        assert "Saldo antes: R$ 220.00" in receipt
        assert "Saldo depois: R$ 200.00" in receipt


def test_falha_durante_persistencia_reverte_pagamento_inteiro():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"; schema(path)
        conn = sqlite3.connect(path); add_customer(conn, 1, "100.00")
        add_sale(conn, 10, 1, "100.00", [("100.00", "0")])
        conn.execute("CREATE TRIGGER bloquear_parcela BEFORE UPDATE ON parcelas BEGIN SELECT RAISE(ABORT,'falha simulada'); END")
        conn.commit(); conn.close()
        with pytest.raises(sqlite3.IntegrityError):
            service_for(path).receber_pagamento_cliente(
                cliente_id=1, valor="20", alvo={"tipo": "AUTO"}, forma_pagamento="PIX", data_pagamento="2026-08-07"
            )
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT saldo_devedor_decimal FROM clientes WHERE id=1").fetchone()[0] == "100.00"
        assert conn.execute("SELECT valor_aberto_decimal FROM movimentacoes WHERE id=10").fetchone()[0] == "100.00"
        assert conn.execute("SELECT valor_pago_decimal FROM parcelas WHERE movimentacao_id=10").fetchone()[0] == "0"
        assert conn.execute("SELECT COUNT(*) FROM movimentacoes WHERE tipo='PAGAMENTO'").fetchone()[0] == 0
        assert conn.execute("SELECT valor_pago_decimal FROM titulos_financeiros WHERE origem_id='10'").fetchone()[0] == "0.00"
        conn.close()
