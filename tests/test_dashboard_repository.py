from __future__ import annotations

import sqlite3
import tempfile
import unittest
from decimal import Decimal
from datetime import datetime
from pathlib import Path

from database import DatabaseManager
from repositories.dashboard_repository import DashboardRepository


class DashboardRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "dashboard.db"
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY,
                codigo TEXT,
                numero_ficha INTEGER,
                nome TEXT,
                cpf TEXT,
                rg TEXT,
                telefone TEXT,
                endereco TEXT,
                saldo_devedor REAL DEFAULT 0
            );
            CREATE TABLE movimentacoes (
                id INTEGER PRIMARY KEY,
                cliente_id INTEGER,
                tipo TEXT,
                descricao TEXT,
                valor REAL,
                data TEXT,
                vencimento TEXT,
                status_pagamento TEXT,
                valor_aberto REAL DEFAULT 0
            );
            CREATE TABLE produtos (
                id INTEGER PRIMARY KEY,
                ativo INTEGER DEFAULT 1
            );
            """
        )
        conn.executemany(
            "INSERT INTO clientes(id,codigo,numero_ficha,nome,saldo_devedor) VALUES(?,?,?,?,?)",
            [
                (1, "C1", 101, "EM DIA", 0),
                (2, "C2", 102, "DEVENDO", 100),
                (3, "C3", 103, "ALERTA", 200),
                (4, "C4", 104, "FUTURO", 312),
            ],
        )
        conn.executemany(
            """INSERT INTO movimentacoes
               (id,cliente_id,tipo,descricao,valor,data,vencimento,status_pagamento,valor_aberto)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            [
                (1, 2, "COMPRA", "VENDA", 100, "02/08/2026 10:00:00", "2026-08-01", "PENDENTE", 100),
                (2, 3, "COMPRA", "VENDA ANTIGA", 200, "02/08/2026 09:00:00", "2026-05-01", "PENDENTE", 200),
                (3, 1, "PAGAMENTO", "RECEBIMENTO", 50, "02/08/2026 11:00:00", "", "PAGO", 0),
                (4, 4, "COMPRA", "VENDA FUTURA", 312, "01/08/2026 12:00:00", "2026-08-30", "PENDENTE", 312),
            ],
        )
        conn.executemany("INSERT INTO produtos(id,ativo) VALUES(?,?)", [(1, 1), (2, 1), (3, 0)])
        conn.commit()
        conn.close()
        self.repo = DashboardRepository(DatabaseManager(self.db_path))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_client_summary_classifies_current_owing_and_alert(self) -> None:
        summary = self.repo.client_summary(now=datetime(2026, 8, 2))
        self.assertEqual(summary.total_records, 4)
        self.assertEqual(summary.current_count, 1)
        self.assertEqual(summary.owing_count, 2)
        self.assertEqual(summary.owing_value, Decimal("412"))
        self.assertIsInstance(summary.owing_value, Decimal)
        self.assertEqual(summary.alert_count, 1)
        self.assertEqual(summary.alert_value, 200)

    def test_cards_return_only_clients_from_the_selected_situation(self) -> None:
        reference = datetime(2026, 8, 2)
        self.assertEqual(self.repo.client_segment_ids("all", now=reference), (1, 2, 3, 4))
        self.assertEqual(self.repo.client_segment_ids("current", now=reference), (1,))
        self.assertEqual(self.repo.client_segment_ids("owing", now=reference), (2, 4))
        self.assertEqual(self.repo.client_segment_ids("alert", now=reference), (3,))
        self.assertEqual(self.repo.client_segment_ids("debt", now=reference), (2, 3, 4))

    def test_card_search_preserves_exact_record_and_name_filter(self) -> None:
        reference = datetime(2026, 8, 2)
        self.assertEqual(self.repo.client_segment_ids("debt", "103", now=reference), (3,))
        self.assertEqual(self.repo.client_segment_ids("debt", "fut", now=reference), (4,))
        self.assertEqual(self.repo.client_segment_ids("current", "alerta", now=reference), ())

    def test_invalid_card_segment_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.client_segment_ids("inventado")

    def test_indicators_include_overdue_and_active_products(self) -> None:
        indicators = self.repo.indicators(now=datetime(2026, 8, 2))
        self.assertEqual(indicators.overdue_count, 2)
        self.assertEqual(indicators.overdue_value, Decimal("300"))
        self.assertIsInstance(indicators.overdue_value, Decimal)
        self.assertEqual(indicators.active_products, 2)

    def test_day_history_preserves_order_and_totals(self) -> None:
        history = self.repo.day_history(day=datetime(2026, 8, 2))
        self.assertEqual([m.movement_id for m in history.movements], [3, 2, 1])
        self.assertEqual(history.sales_total, Decimal("300"))
        self.assertIsInstance(history.movements[0].value, Decimal)
        self.assertEqual(history.received_total, 50)
        self.assertEqual(history.movement_total, 350)

    def test_daily_credit_flow_separates_down_payment_and_financed_value(self) -> None:
        flow = self.repo.daily_credit_flow(day=datetime(2026, 8, 2))
        self.assertEqual(flow.received_total, Decimal("50"))
        self.assertEqual(flow.financed_total, Decimal("300"))
        self.assertEqual([entry.movement_id for entry in flow.entries], [3, 2, 1])

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO movimentacoes VALUES(5,1,'COMPRA','VENDA 500',500,"
            "'02/08/2026 12:00:00','2026-09-01','PENDENTE',400)"
        )
        conn.commit(); conn.close()
        flow = self.repo.daily_credit_flow(day=datetime(2026, 8, 2))
        self.assertEqual(flow.received_total, Decimal("150"))
        self.assertEqual(flow.financed_total, Decimal("700"))

    def test_daily_credit_flow_preserves_original_credit_after_later_payment(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE parcelas (
                id INTEGER PRIMARY KEY,
                movimentacao_id INTEGER,
                valor_parcela REAL,
                valor_pago REAL DEFAULT 0
            );
            UPDATE movimentacoes SET valor=500, valor_aberto=250 WHERE id=1;
            INSERT INTO parcelas(movimentacao_id,valor_parcela,valor_pago)
            VALUES(1,200,75),(1,200,75);
            """
        )
        conn.commit(); conn.close()
        flow = self.repo.daily_credit_flow(day=datetime(2026, 8, 2))
        sale = next(entry for entry in flow.entries if entry.movement_id == 1)
        self.assertEqual(sale.received_value, Decimal("100"))
        self.assertEqual(sale.financed_value, Decimal("400"))

    def test_daily_flow_cash_sale_credit_and_receipts_do_not_duplicate(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("ALTER TABLE movimentacoes ADD COLUMN forma_pagamento TEXT")
        conn.execute("DELETE FROM movimentacoes")
        conn.executemany(
            "INSERT INTO movimentacoes(id,cliente_id,tipo,valor,data,status_pagamento,valor_aberto,forma_pagamento) VALUES(?,?,?,?,?,?,?,?)",
            [(1,1,"COMPRA",500,"02/08/2026 10:00","PAGO",0,"DINHEIRO R$ 100.00 + CREDIARIO R$ 400.00"),
             (2,1,"COMPRA",250,"2026-08-02 11:00","PAGO",0,"PIX R$ 250.00"),
             (3,1,"PAGAMENTO",400,"02/08/2026 12:00","PAGO",0,"PIX"),
             (4,1,"COMPRA",999,"02/08/2026 13:00","CANCELADO",0,"PIX")],
        )
        conn.commit(); conn.close()
        flow = self.repo.daily_credit_flow(day=datetime(2026, 8, 2))
        self.assertEqual(flow.received_total, Decimal("750"))
        self.assertEqual(flow.financed_total, Decimal("400"))

    def test_missing_products_table_returns_unavailable_indicator(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DROP TABLE produtos")
            conn.commit()
        finally:
            conn.close()
        indicators = self.repo.indicators(now=datetime(2026, 8, 2))
        self.assertIsNone(indicators.active_products)


if __name__ == "__main__":
    unittest.main()
