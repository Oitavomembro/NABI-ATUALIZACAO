import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class NativePrintDialogRegressionTests(unittest.TestCase):
    def test_pdf_actions_use_native_dialog_not_custom_toplevel(self):
        block = SOURCE.split("def janela_acoes_pdf", 1)[1].split("def imprimir_pdf_configurado", 1)[0]
        self.assertIn("messagebox.askyesnocancel", block)
        self.assertNotIn("CTkToplevel", block)
        self.assertNotIn("tk.Toplevel", block)
        self.assertIn("_parent_dialogo_ativo", block)

    def test_three_actions_are_explicit(self):
        block = SOURCE.split("def janela_acoes_pdf", 1)[1].split("def imprimir_pdf_configurado", 1)[0]
        self.assertIn("Sim: imprimir", block)
        self.assertIn("Não: abrir o PDF", block)
        self.assertIn("Cancelar: fechar", block)
        self.assertIn("resposta is True", block)
        self.assertIn("resposta is False", block)

    def test_source_is_syntactically_valid(self):
        ast.parse(SOURCE)


if __name__ == "__main__":
    unittest.main()
