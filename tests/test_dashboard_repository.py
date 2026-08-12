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
                nome TEXT,
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
            "INSERT INTO clientes(id,nome,saldo_devedor) VALUES(?,?,?)",
            [(1, "EM DIA", 0), (2, "DEVENDO", 100), (3, "ALERTA", 200), (4, "FUTURO", 312)],
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
