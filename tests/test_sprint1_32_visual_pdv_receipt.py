from __future__ import annotations

import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from services.pdf_document_service import PDFDocumentService


class Sprint132SourceRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.legacy = (root / "nabicode_legacy.py").read_text(encoding="utf-8")
        cls.splash = (root / "splash_screen.py").read_text(encoding="utf-8")

    def test_splash_reuses_the_pygame_display_surface(self):
        self.assertEqual(self.splash.count("self.pygame.display.set_mode("), 1)
        self.assertIn("self.screen.fill(self.engine.SPACE)", self.splash)
        self.assertIn("self.pygame.display.flip()", self.splash)
        self.assertNotIn("tkinter", self.splash)
        self.assertEqual(int(self.splash.split("STAR_COUNT =", 1)[1].splitlines()[0].strip()), 2050)

    def test_pdv_is_hidden_until_layout_is_ready(self):
        self.assertIn("prepare_hidden_toplevel(win)", self.legacy)
        self.assertIn("def revelar_pdv_pronto", self.legacy)
        self.assertIn("reveal_prepared_toplevel_when_idle(", self.legacy)
        construction = self.legacy.split("def abrir_pdv_independente", 1)[1].split("def revelar_pdv_pronto", 1)[0]
        self.assertNotIn('win.state("zoomed")', construction)
        self.assertNotIn("win.deiconify()", construction)

    def test_product_suggestions_use_stable_native_popup(self):
        display = self.legacy.split("def exibir_sugestoes_produto", 1)[1].split("def _cancelar_fechamento_sugestoes_produto", 1)[0]
        self.assertIn("tk.Toplevel", display)
        self.assertIn("ttk.Treeview", display)
        self.assertIn("min(10, len(sugestoes))", display)
        self.assertIn('font=("Segoe UI", 11)', display)
        self.assertNotIn("def _criar_lista_produtos_inline", self.legacy)



class Sprint132PaymentPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "test.db"
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE movimentacoes (
                id INTEGER PRIMARY KEY,
                forma_pagamento TEXT,
                total_parcelas INTEGER,
                valor_aberto REAL,
                valor_aberto_decimal TEXT,
                status_pagamento TEXT
            );
            CREATE TABLE parcelas (
                id INTEGER PRIMARY KEY,
                movimentacao_id INTEGER,
                numero_parcela INTEGER,
                valor_parcela REAL,
                valor_parcela_decimal TEXT,
                vencimento TEXT,
                status TEXT
            );
            INSERT INTO movimentacoes VALUES (10, 'CREDIARIO', 3, 30.0, '30.00', 'PENDENTE');
            INSERT INTO parcelas VALUES (1, 10, 1, 10.0, '10.00', '2026-09-05', 'PENDENTE');
            INSERT INTO parcelas VALUES (2, 10, 2, 10.0, '10.00', '2026-10-05', 'PENDENTE');
            INSERT INTO parcelas VALUES (3, 10, 3, 10.0, '10.00', '2026-11-05', 'PENDENTE');
            """
        )
        conn.commit()
        conn.close()
        self.service = PDFDocumentService(
            connection_factory=lambda: sqlite3.connect(self.db_path),
            config_getter=lambda _key: "",
            pdf_dir=self.temp.name,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_sale_payment_plan_contains_installments_and_due_dates(self):
        plan = self.service._sale_payment_plan(10)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["forma"], "CREDIARIO")
        self.assertEqual(plan["valor_aberto"], Decimal("30.00"))
        self.assertEqual([item["numero"] for item in plan["parcelas"]], [1, 2, 3])
        self.assertEqual(
            [item["vencimento"] for item in plan["parcelas"]],
            ["2026-09-05", "2026-10-05", "2026-11-05"],
        )

    def test_venda_em_dinheiro_nao_imprime_parcela_tecnica_residual(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO movimentacoes VALUES (11, 'DINHEIRO R$ 5.11', 1, 0, '0.00', 'PAGO')"
        )
        conn.execute(
            "INSERT INTO parcelas VALUES (4, 11, 1, 5.11, '5.11', '2026-08-29', 'PAGO')"
        )
        conn.commit()
        conn.close()

        plan = self.service._sale_payment_plan(11)

        self.assertEqual(plan["forma"], "DINHEIRO R$ 5.11")
        self.assertFalse(plan["financiado"])
        self.assertEqual(plan["parcelas"], [])
        self.assertEqual(plan["valor_aberto"], Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
