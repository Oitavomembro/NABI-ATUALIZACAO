import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class UnifiedPrintDialogRegressionTests(unittest.TestCase):
    def test_windows_pdf_printer_is_explicitly_imported(self):
        tree = ast.parse(SOURCE)
        imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "services.windows_pdf_printer"
            for alias in node.names
        }
        self.assertIn("WindowsPDFPrinter", imports)
        self.assertIn("WindowsPDFPrintError", imports)

    def test_all_pdf_actions_use_native_three_choice_contract(self):
        block = SOURCE.split("def janela_acoes_pdf", 1)[1].split("def imprimir_pdf_configurado", 1)[0]
        self.assertIn("messagebox.askyesnocancel", block)
        self.assertIn("Sim: imprimir", block)
        self.assertIn("Não: abrir o PDF", block)
        self.assertIn("Cancelar: fechar", block)
        self.assertNotIn("CTkToplevel", block)
        self.assertNotIn("tk.Toplevel", block)

    def test_reprint_path_calls_unified_preview_dialog(self):
        block = SOURCE.split("def reimprimir_movimentacao", 1)[1].split("def ", 1)[0]
        self.assertIn("janela_preview_documento", block)
        self.assertNotIn("janela_acoes_pdf(caminho", block)

    def test_runtime_printer_name_cannot_be_missing(self):
        compile(SOURCE, "nabicode_legacy.py", "exec")


if __name__ == "__main__":
    unittest.main()
