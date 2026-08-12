from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile

from services.financeiro_calculator import FinanceiroCalculator
from tests.test_financeiro_reconciliacao_2490 import (
    add_customer,
    add_sale,
    schema,
    service_for,
)


def test_saldo_90_pagamento_20_resulta_70():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        schema(path)
        conn = sqlite3.connect(path)
        add_customer(conn, 1, "90.00")
        add_sale(conn, 10, 1, "90.00", [("90.00", "0.00")])
        conn.commit(); conn.close()

        result = service_for(path).receber_pagamento_cliente(
            cliente_id=1, valor="20.00", alvo=None, forma_pagamento="PIX", data_pagamento="2026-08-07"
        )
        assert result["saldo_anterior"] == Decimal("90.00")
        assert result["novo_saldo"] == Decimal("70.00")


def test_saldo_220_pagamento_20_permanece_reconciliado_em_200():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        schema(path)
        conn = sqlite3.connect(path)
        add_customer(conn, 1, "220.00")
        add_sale(conn, 10, 1, "120.00", [("60.00", "0"), ("60.00", "0")])
        add_sale(conn, 11, 1, "100.00", [("50.00", "0"), ("50.00", "0")])
        conn.commit(); conn.close()

        result = service_for(path).receber_pagamento_cliente(
            cliente_id=1, valor="20", alvo=None, forma_pagamento="DINHEIRO", data_pagamento="2026-08-07"
        )
        assert result["novo_saldo"] == Decimal("200.00")
        assert service_for(path).reconciliar_cliente(1)["saldo_real"] == Decimal("200.00")


def test_saldo_historico_sem_compras_detalhadas_aceita_pagamento():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        schema(path)
        conn = sqlite3.connect(path)
        add_customer(conn, 1, "150.00")
        conn.commit(); conn.close()

        result = service_for(path).receber_pagamento_cliente(
            cliente_id=1, valor="20", alvo=None, forma_pagamento="PIX", data_pagamento="2026-08-07"
        )
        assert result["saldo_anterior"] == Decimal("150.00")
        assert result["novo_saldo"] == Decimal("130.00")
        assert result["alocacoes"] == [{
            "tipo": "SALDO_LEGADO",
            "valor_aplicado": Decimal("20.00"),
            "saldo_antes": Decimal("150.00"),
            "saldo_depois": Decimal("130.00"),
            "parcelas_aplicadas": [],
        }]


def test_reconciliacao_e_idempotente_e_persiste_apos_reinicio():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        schema(path)
        conn = sqlite3.connect(path)
        add_customer(conn, 1, "150.00")
        add_sale(conn, 10, 1, "150.00", [("100.00", "0"), ("100.00", "0")])
        conn.commit(); conn.close()

        service = service_for(path)
        primeira = service.reconciliar_cliente(1)
        segunda = service.reconciliar_cliente(1)
        reiniciado = service_for(path).reconciliar_cliente(1)

        assert primeira["saldo_real"] == segunda["saldo_real"] == reiniciado["saldo_real"] == Decimal("150.00")
        assert segunda["ajustes_parcelas"] == []
        assert reiniciado["ajustes_parcelas"] == []


def test_um_recebimento_nao_gera_dupla_baixa():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite"
        schema(path)
        conn = sqlite3.connect(path)
        add_customer(conn, 1, "100.00")
        add_sale(conn, 10, 1, "100.00", [("100.00", "0")])
        conn.commit(); conn.close()

        service_for(path).receber_pagamento_cliente(
            cliente_id=1, valor="20", alvo=None, forma_pagamento="PIX", data_pagamento="2026-08-07"
        )
        conn = sqlite3.connect(path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM movimentacoes WHERE tipo='PAGAMENTO'").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM pagamentos_titulos").fetchone()[0] == 1
            assert Decimal(conn.execute("SELECT valor_pago_decimal FROM titulos_financeiros WHERE origem_id='10'").fetchone()[0]) == Decimal("20")
        finally:
            conn.close()


def test_calculadora_saldo_parcelas_usa_decimal_exato():
    parcelas = [
        {"valor_parcela": "33.33", "valor_pago": "3.33"},
        {"valor_parcela": "66.67", "valor_pago": "6.67"},
    ]
    assert FinanceiroCalculator.saldo_parcelas(parcelas) == Decimal("90.00")
