from __future__ import annotations

import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from services.report_service import ReportService


class ReportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE movimentacoes(
                id INTEGER PRIMARY KEY, data TEXT, tipo TEXT, cliente TEXT,
                valor_total REAL, forma_pagamento TEXT, status TEXT, usuario TEXT
            );
            CREATE TABLE financeiro_titulos(
                id INTEGER PRIMARY KEY, tipo TEXT, pessoa_nome TEXT, descricao TEXT,
                data_emissao TEXT, data_vencimento TEXT, valor_original REAL,
                valor_pago REAL, saldo_aberto REAL, status TEXT, origem TEXT, origem_id TEXT
            );
            CREATE TABLE produtos(
                id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, preco_custo REAL,
                preco_venda REAL, estoque_atual REAL, estoque_minimo REAL,
                controla_estoque INTEGER, ativo INTEGER, atualizado_em TEXT
            );
            CREATE TABLE clientes(id INTEGER PRIMARY KEY, nome TEXT, saldo_devedor REAL, ativo INTEGER);
            """
        )
        connection.execute(
            "INSERT INTO movimentacoes VALUES(1,'2026-08-01 10:00:00','VENDA','ANA',125.50,'PIX','PAGO','admin')"
        )
        connection.execute(
            "INSERT INTO movimentacoes VALUES(2,'2026-07-01 10:00:00','VENDA','JOAO',75,'DINHEIRO','PAGO','operador')"
        )
        connection.execute(
            "INSERT INTO movimentacoes VALUES(3,'2026-08-02 10:00:00','COMPRA','BIA',50,'CREDIARIO','PENDENTE','admin')"
        )
        connection.execute(
            "INSERT INTO movimentacoes VALUES(4,'2026-08-03 10:00:00','PAGAMENTO','ANA',125.50,'PIX','PAGO','admin')"
        )
        connection.execute(
            "INSERT INTO movimentacoes VALUES(5,'04/08/2026 10:00:00','VENDA','BIA',30,'DINHEIRO','PAGO','admin')"
        )
        connection.execute(
            "INSERT INTO financeiro_titulos VALUES(1,'RECEBER','ANA','Venda','2026-08-01','2026-08-10',200,50,150,'PARCIAL','VENDA','1')"
        )
        connection.execute(
            "INSERT INTO financeiro_titulos VALUES(2,'PAGAR','FORNECEDOR','Compra','2026-08-01','2026-08-15',300,0,300,'ABERTO','COMPRA','4')"
        )
        connection.execute(
            "INSERT INTO produtos VALUES(1,'P1','PRODUTO',10,20,2,5,1,1,'2026-08-01')"
        )
        connection.execute("INSERT INTO clientes VALUES(1,'ANA',150,1)")
        connection.commit()
        connection.close()
        self.audit_events = []

        def connect():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

        self.service = ReportService(
            connect,
            output_dir=Path(self.tmp.name) / "reports",
            audit=lambda *args: self.audit_events.append(args),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_generate_applies_date_search_status_and_user_filters(self) -> None:
        result = self.service.generate(
            "vendas",
            start_date="2026-08-01",
            end_date="2026-08-31",
            search="ANA",
            status="PAGO",
            user="admin",
            actor="admin",
        )
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.rows[0][0], 1)
        self.assertTrue(self.audit_events)

    def test_indicators_do_not_count_pending_movements_as_sales(self) -> None:
        data = self.service.indicators(start_date="2026-08-01", end_date="2026-08-31")
        self.assertEqual(data["vendas_quantidade"], 3)
        self.assertEqual(data["vendas_total"], 205.50)
        self.assertEqual(data["receber_aberto"], 150)
        self.assertEqual(data["pagar_aberto"], 300)
        self.assertEqual(data["estoque_baixo"], 1)
        self.assertEqual(data["clientes_ativos"], 1)

    def test_relatorio_de_vendas_exclui_pagamento_de_ficha(self) -> None:
        result = self.service.generate(
            "vendas", start_date="2026-08-01", end_date="2026-08-31", actor="admin"
        )
        type_index = result.columns.index("tipo")
        self.assertEqual({row[type_index] for row in result.rows}, {"VENDA", "COMPRA"})
        self.assertNotIn("PAGAMENTO", {row[type_index] for row in result.rows})

    def test_datas_brasileiras_e_resumo_do_periodo(self) -> None:
        result = self.service.generate(
            "vendas", start_date="01/08/2026", end_date="31/08/2026", actor="admin"
        )
        self.assertEqual(result.row_count, 3)
        self.assertEqual(
            self.service.result_summary(result),
            {"quantidade": 3, "valor_total": Decimal("205.5")},
        )

    def test_recebimentos_tem_total_separado_do_faturamento(self) -> None:
        result = self.service.generate(
            "recebimentos", start_date="01/08/2026", end_date="31/08/2026", actor="admin"
        )
        type_index = result.columns.index("tipo")
        self.assertEqual({row[type_index] for row in result.rows}, {"PAGAMENTO"})
        self.assertEqual(
            self.service.result_summary(result),
            {"quantidade": 1, "valor_total": Decimal("125.5")},
        )

    def test_exports_csv_xlsx_and_pdf(self) -> None:
        result = self.service.generate("financeiro", actor="admin")
        for fmt, suffix in (("CSV", ".csv"), ("XLSX", ".xlsx"), ("PDF", ".pdf")):
            path = self.service.export(result, fmt, actor="admin")
            self.assertTrue(path.exists())
            self.assertEqual(path.suffix, suffix)
            self.assertGreater(path.stat().st_size, 0)

    def test_history_is_persisted_and_clearable(self) -> None:
        result = self.service.generate("produtos", actor="admin")
        self.service.export(result, "CSV", actor="admin")
        history = self.service.history()
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0]["format"], "CSV")
        self.service.clear_history(actor="admin")
        self.assertEqual(self.service.history(), [])

    def test_schedule_can_be_saved_run_and_deleted(self) -> None:
        saved = self.service.save_schedule(
            {
                "name": "Resumo mensal",
                "report_id": "vendas",
                "frequency": "MENSAL",
                "format": "CSV",
                "active": True,
                "filters": {"start_date": "2026-08-01", "end_date": "2026-08-31"},
            },
            actor="admin",
        )
        self.assertEqual(saved["report_id"], "vendas")
        path = self.service.run_schedule("Resumo mensal", actor="admin")
        self.assertTrue(path.exists())
        self.service.delete_schedule("Resumo mensal", actor="admin")
        self.assertEqual(self.service.list_schedules(), [])

    def test_invalid_report_and_schedule_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.service.generate("inexistente")
        with self.assertRaises(ValueError):
            self.service.save_schedule({"name": "x", "report_id": "vendas", "frequency": "HORARIA", "format": "CSV"})

    def test_chart_series_and_dashboard_are_generated(self) -> None:
        result = self.service.generate("vendas", actor="admin")
        series = self.service.chart_series(result)
        self.assertTrue(series["labels"])
        self.assertEqual(len(series["labels"]), len(series["values"]))
        dashboard = self.service.dashboard(start_date="2026-08-01", end_date="2026-08-31")
        self.assertIn("indicators", dashboard)
        self.assertIn("sales_chart", dashboard)

    def test_due_schedule_runs_and_advances_next_execution(self) -> None:
        saved = self.service.save_schedule(
            {
                "name": "Diário vencido",
                "report_id": "vendas",
                "frequency": "DIARIO",
                "run_time": "08:00",
                "format": "CSV",
                "active": True,
                "filters": {},
                "next_run_at": "2026-08-01T08:00",
            },
            actor="admin",
        )
        generated = self.service.run_due_schedules(now=datetime(2026, 8, 2, 9, 0), actor="admin")
        self.assertEqual(len(generated), 1)
        updated = self.service.list_schedules()[0]
        self.assertTrue(updated["last_run_at"])
        self.assertGreater(updated["next_run_at"], saved["next_run_at"])

    def test_failed_due_schedule_does_not_block_the_next_one(self) -> None:
        for name in ("A falha", "B funciona"):
            self.service.save_schedule({
                "name": name, "report_id": "vendas", "frequency": "DIARIO",
                "run_time": "08:00", "format": "CSV", "active": True,
                "next_run_at": "2026-08-01T08:00",
            }, actor="admin")
        generated_path = Path(self.tmp.name) / "segundo.csv"

        def run(name, *, actor):
            if name == "A falha":
                raise RuntimeError("falha simulada")
            return generated_path

        with patch.object(self.service, "run_schedule", side_effect=run):
            generated = self.service.run_due_schedules(
                now=datetime(2026, 8, 2, 9, 0), actor="admin"
            )
        self.assertEqual(generated, [generated_path])
        errors = [event for event in self.audit_events if event[1] == "EXECUTAR_AGENDAMENTO"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][2], "A falha")
        self.assertEqual(errors[0][4], "ERRO")

    def test_schedule_rejects_invalid_time(self) -> None:
        with self.assertRaises(ValueError):
            self.service.save_schedule({"name": "x", "report_id": "vendas", "frequency": "DIARIO", "run_time": "25:90", "format": "CSV"})

    def test_custom_indicator_can_be_saved_evaluated_and_deleted(self) -> None:
        saved = self.service.save_custom_indicator(
            {"name": "Total vendido", "report_id": "vendas", "aggregation": "SUM", "column": "valor_total", "filters": {"status": "PAGO"}},
            actor="admin",
        )
        self.assertEqual(saved["aggregation"], "SUM")
        evaluated = self.service.evaluate_custom_indicators(start_date="2026-08-01", end_date="2026-08-31")
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(evaluated[0]["value"], Decimal("155.5"))
        dashboard = self.service.dashboard(start_date="2026-08-01", end_date="2026-08-31")
        self.assertEqual(dashboard["custom_indicators"][0]["name"], "Total vendido")
        self.service.delete_custom_indicator("Total vendido", actor="admin")
        self.assertEqual(self.service.list_custom_indicators(), [])

    def test_custom_indicator_rejects_invalid_column(self) -> None:
        with self.assertRaises(ValueError):
            self.service.save_custom_indicator({"name": "x", "report_id": "vendas", "aggregation": "SUM", "column": "inexistente"})

    def test_print_pdf_exports_and_dispatches(self) -> None:
        result = self.service.generate("vendas", actor="admin")
        with patch.object(self.service, "_dispatch_print") as dispatch:
            path = self.service.print_pdf(result, actor="admin", dispatch=True)
        self.assertTrue(path.exists())
        dispatch.assert_called_once_with(path)

    def test_malformed_history_shape_is_recovered_on_next_export(self) -> None:
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
            (ReportService.HISTORY_KEY, '{"formato":"antigo"}'),
        )
        connection.commit()
        connection.close()
        self.assertEqual(self.service.history(), [])
        result = self.service.generate("vendas", actor="admin")
        self.service.export(result, "CSV", actor="admin")
        history = self.service.history()
        self.assertEqual(len(history), 2)
        self.assertTrue(all(isinstance(item, dict) for item in history))

    def test_failed_export_preserves_existing_destination_and_removes_partial(self) -> None:
        destination = Path(self.tmp.name) / "reports" / "vendas.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("arquivo anterior", encoding="utf-8")
        result = self.service.generate("vendas", actor="admin")

        def fail(_result, temporary_path):
            temporary_path.write_text("parcial", encoding="utf-8")
            raise OSError("falha simulada")

        with patch.object(self.service, "_export_csv", side_effect=fail):
            with self.assertRaisesRegex(OSError, "falha simulada"):
                self.service.export(result, "CSV", destination, actor="admin")
        self.assertEqual(destination.read_text(encoding="utf-8"), "arquivo anterior")
        self.assertEqual(list(destination.parent.glob("vendas.*.csv")), [])

    def test_empty_export_is_rejected_before_replacing_destination(self) -> None:
        destination = Path(self.tmp.name) / "reports" / "vendas.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("arquivo anterior", encoding="utf-8")
        result = self.service.generate("vendas", actor="admin")
        with patch.object(self.service, "_export_csv", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "arquivo válido"):
                self.service.export(result, "CSV", destination, actor="admin")
        self.assertEqual(destination.read_text(encoding="utf-8"), "arquivo anterior")
        self.assertEqual(list(destination.parent.glob("vendas.*.csv")), [])

    def test_windows_pdf_dispatch_uses_isolated_printer(self) -> None:
        path = Path(self.tmp.name) / "relatorio.pdf"
        path.write_bytes(b"%PDF-1.4\n")
        with patch("services.report_service.sys.platform", "win32"), patch(
            "services.report_service.WindowsPDFPrinter"
        ) as printer_class:
            ReportService._dispatch_print(path)
        printer_class.return_value.print.assert_called_once_with(
            path, "Padrão do Sistema"
        )

    def test_schedule_preserves_filters_and_can_be_disabled(self) -> None:
        saved = self.service.save_schedule({
            "name": "Vendas filtradas", "report_id": "vendas", "frequency": "DIARIO", "run_time": "08:00", "format": "CSV",
            "active": True, "filters": {"status": "PAGO", "user": "admin"},
        }, actor="admin")
        self.assertEqual(saved["filters"]["status"], "PAGO")
        disabled = self.service.save_schedule({**saved, "active": False}, actor="admin")
        self.assertFalse(disabled["active"])
        self.assertEqual(self.service.run_due_schedules(now=datetime(2030, 1, 1, 9, 0)), [])

    def test_malformed_schedules_do_not_block_valid_entries(self) -> None:
        valid = self.service.save_schedule({
            "name": "Vendas diárias", "report_id": "vendas",
            "frequency": "DIARIO", "format": "CSV", "active": False,
        })
        connection = sqlite3.connect(self.db_path)
        rows = [
            valid,
            "entrada antiga",
            {"name": "Sem relatório", "frequency": "DIARIO", "format": "CSV"},
            {"name": "Formato ruim", "report_id": "vendas", "frequency": "DIARIO", "format": "TXT"},
        ]
        import json
        connection.execute(
            "UPDATE configuracoes SET valor=? WHERE chave=?",
            (json.dumps(rows), ReportService.SCHEDULES_KEY),
        )
        connection.commit()
        connection.close()
        schedules = self.service.list_schedules()
        self.assertEqual([item["name"] for item in schedules], ["Vendas diárias"])
        self.assertEqual(self.service.run_due_schedules(now=datetime(2030, 1, 1, 9, 0)), [])

    def test_authorizer_blocks_unauthorized_report(self) -> None:
        service = ReportService(
            self.service.connection_factory,
            output_dir=Path(self.tmp.name) / "authorized_reports",
            authorize=lambda actor, report_id: report_id != "financeiro",
        )
        service.generate("vendas", actor="operador")
        with self.assertRaises(PermissionError):
            service.generate("financeiro", actor="operador")

    def test_monthly_schedule_preserves_day_or_clamps_to_month_end(self) -> None:
        next_run = self.service._next_run_at("MENSAL", "08:00", datetime(2026, 1, 31, 9, 0))
        self.assertEqual(next_run.date().isoformat(), "2026-02-28")
        regular = self.service._next_run_at("MENSAL", "08:00", datetime(2026, 3, 15, 9, 0))
        self.assertEqual(regular.date().isoformat(), "2026-04-15")


if __name__ == "__main__":
    unittest.main()

class ReportDecimalPrecisionTests(unittest.TestCase):
    def test_indicators_return_decimal(self):
        from decimal import Decimal
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decimal.db"
            conn = sqlite3.connect(path)
            conn.executescript("""
                CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, data TEXT, tipo TEXT, valor_total REAL);
                CREATE TABLE financeiro_titulos(id INTEGER PRIMARY KEY, tipo TEXT, status TEXT, valor_original REAL, valor_pago REAL);
                INSERT INTO movimentacoes VALUES(1,'2026-08-01 10:00:00','VENDA',0.1);
                INSERT INTO financeiro_titulos VALUES(1,'RECEBER','ABERTO',0.3,0.1);
            """)
            conn.commit(); conn.close()
            service = ReportService(lambda: sqlite3.connect(path), output_dir=Path(tmp) / "out")
            data = service.indicators(start_date="2026-08-01", end_date="2026-08-31")
            self.assertIsInstance(data["vendas_total"], Decimal)
            self.assertIsInstance(data["receber_aberto"], Decimal)
            self.assertEqual(data["vendas_total"], Decimal("0.1"))
            self.assertEqual(data["receber_aberto"], Decimal("0.19999999999999998"))
