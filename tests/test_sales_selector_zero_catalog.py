from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class SalesSelectorZeroCatalogTests(unittest.TestCase):
    def test_empty_search_can_show_catalog_or_avulso_message(self):
        block = SOURCE[
            SOURCE.index("    def mostrar_lista_produtos_venda"):
            SOURCE.index("    def filtrar_produtos_venda")
        ]
        self.assertIn("permitir_avulso=True", block)

    def test_unmatched_term_creates_avulso_option(self):
        prepare = SOURCE[
            SOURCE.index("    def _preencher_sugestoes_produto"):
            SOURCE.index("    def exibir_sugestoes_produto")
        ]
        self.assertIn('"_avulso": True', prepare)
        self.assertIn("USAR COMO PRODUTO AVULSO", prepare)

    def test_avulso_selection_enables_checkbox_and_price_focus(self):
        block = SOURCE[
            SOURCE.index("    def confirmar_sugestao_produto"):
            SOURCE.index("    def fechar_sugestoes_produto")
        ]
        self.assertIn("self.var_item_avulso_pdv.set(True)", block)
        self.assertIn("self.entry_valor_venda.focus_set()", block)

    def test_selector_uses_native_popup_and_explicit_button(self):
        display = SOURCE[
            SOURCE.index("    def exibir_sugestoes_produto"):
            SOURCE.index("    def _cancelar_fechamento_sugestoes_produto")
        ]
        self.assertNotIn("def _criar_lista_produtos_inline", SOURCE)
        self.assertIn("tk.Toplevel", display)
        self.assertIn("ttk.Treeview", display)
        self.assertIn("command=self.mostrar_lista_produtos_venda", SOURCE)
        self.assertIn("_sincronizar_contexto_item_venda", SOURCE)



if __name__ == "__main__":
    unittest.main()
