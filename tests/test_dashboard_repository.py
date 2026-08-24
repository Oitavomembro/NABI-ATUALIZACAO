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

    def test_day_history_page_limits_rows_but_preserves_full_day_totals(self) -> None:
        first = self.repo.day_history_page(day=datetime(2026, 8, 2), limit=2)
        second = self.repo.day_history_page(day=datetime(2026, 8, 2), limit=2, offset=2)
        self.assertEqual([item.movement_id for item in first.movements], [3, 2])
        self.assertEqual([item.movement_id for item in second.movements], [1])
        self.assertEqual(first.total_records, 3)
        self.assertEqual(first.sales_total, Decimal("300"))
        self.assertEqual(first.received_total, Decimal("50"))
        self.assertEqual((first.limit, first.offset), (2, 0))

    def test_day_history_page_with_volume_never_materializes_more_than_limit(self) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executemany(
                """INSERT INTO movimentacoes
                   (id,cliente_id,tipo,descricao,valor,data,vencimento,status_pagamento,valor_aberto)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                ((index, 1, "COMPRA", "VOLUME", 1, "02/08/2026 12:00:00", "", "PAGO", 0)
                 for index in range(10, 5010)),
            )
            connection.commit()
        finally:
            connection.close()
        page = self.repo.day_history_page(day=datetime(2026, 8, 2), limit=50)
        self.assertEqual(len(page.movements), 50)
        self.assertEqual(page.total_records, 5003)
        self.assertEqual(page.sales_total, Decimal("5300"))

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
