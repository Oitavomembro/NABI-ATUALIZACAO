from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from services.windows_pdf_printer import WindowsPDFPrinter, WindowsPDFPrintError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class WindowsPDFPrinterTests(unittest.TestCase):
    def test_default_printer_uses_external_powershell_not_startfile(self):
        runner = Mock()
        service = WindowsPDFPrinter(runner=runner, is_windows=True)
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "cupom.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            result = service.print(pdf, "Padrão do Sistema")
        self.assertEqual(result, "Padrão do Sistema")
        command = runner.call_args.args[0]
        self.assertEqual(command[:4], ["powershell", "-NoProfile", "-NonInteractive", "-Command"])
        self.assertIn("-Verb Print", command[-1])
        self.assertNotIn("os.startfile", command[-1])

    def test_named_printer_uses_printto(self):
        service = WindowsPDFPrinter(runner=Mock(), is_windows=True)
        command = service.command("C:/tmp/cupom.pdf", "EPSON TM-T20")
        self.assertIn("-Verb PrintTo", command[-1])
        self.assertIn("EPSON TM-T20", command[-1])

    def test_failure_is_domain_error(self):
        runner = Mock(side_effect=OSError("shell failure"))
        service = WindowsPDFPrinter(runner=runner, is_windows=True)
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "cupom.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            with self.assertRaises(WindowsPDFPrintError):
                service.print(pdf, "Padrão do Sistema")


class PDVVisualContractTests(unittest.TestCase):
    def test_post_sale_modal_has_exact_three_explicit_actions(self):
        block = SOURCE.split("def janela_venda_finalizada", 1)[1].split(
            "def emitir_venda_conforme_perfil", 1
        )[0]
        self.assertIn("SIM — imprimir cupom 80 mm", block)
        self.assertIn("Finalizar", block)
        self.assertIn("Gerar PDF", block)
        self.assertNotIn("askyesnocancel", block)

    def test_product_selector_has_real_columns_and_system_font(self):
        block = SOURCE.split("def exibir_sugestoes_produto", 1)[1].split(
            "def _cancelar_fechamento_sugestoes_produto", 1
        )[0]
        for heading in ("Código", "Produto / Serviço", "Preço", "Estoque"):
            self.assertIn(heading, block)
        self.assertIn('(\"Segoe UI\", 11)', block)
        self.assertIn('rowheight=30', block)
        self.assertIn('ttk.Treeview(', block)

    def test_legacy_never_prints_pdf_with_os_startfile_verb(self):
        self.assertNotIn('os.startfile(caminho_pdf, "print")', SOURCE)
        self.assertNotIn("os.startfile(caminho_pdf, 'print')", SOURCE)


if __name__ == "__main__":
    unittest.main()
