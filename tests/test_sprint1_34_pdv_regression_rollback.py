from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class Sprint134PDVRegressionTests(unittest.TestCase):
    def test_pos_sale_does_not_create_custom_blank_modal(self):
        block = SOURCE.split("def janela_pos_venda_comprovante", 1)[1].split("def cancelar_venda_pdv", 1)[0]
        self.assertIn("_abrir_arquivo_sistema(caminho_pdf)", block)
        self.assertNotIn("Toplevel(", block)
        self.assertNotIn("wait_window", block)

    def test_product_popup_uses_compact_native_listbox(self):
        display = SOURCE.split("def exibir_sugestoes_produto", 1)[1].split("def _cancelar_fechamento_sugestoes_produto", 1)[0]
        self.assertIn("tk.Toplevel", display)
        self.assertIn("ttk.Treeview", display)
        self.assertIn("min(10, len(sugestoes))", display)


    def test_dashboard_has_no_horizontal_scroll_regression(self):
        block = SOURCE.split("Histórico de Movimentações do Dia", 1)[1].split("return frame", 1)[0]
        self.assertNotIn("dash_scroll_x", block)
        self.assertNotIn("xscrollcommand", block)

    def test_generic_pdf_action_uses_native_dialog_without_blank_toplevel(self):
        block = SOURCE.split("def janela_acoes_pdf", 1)[1].split("def imprimir_pdf_configurado", 1)[0]
        self.assertIn("messagebox.askyesnocancel", block)
        self.assertIn("_parent_dialogo_ativo", block)
        self.assertNotIn("ctk.CTkToplevel", block)
        self.assertNotIn("tk.Toplevel", block)
        self.assertNotIn("wait_window", block)



if __name__ == "__main__":
    unittest.main()
