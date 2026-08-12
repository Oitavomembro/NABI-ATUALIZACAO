from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")

class PDVContextRegressionLockTests(unittest.TestCase):
    def test_both_sales_surfaces_register_their_own_widgets(self):
        self.assertGreaterEqual(SOURCE.count("self._registrar_contexto_item_venda("), 2)
        self.assertIn("var_item_avulso_aba_vendas", SOURCE)

    def test_selector_synchronizes_visible_or_focused_context(self):
        block = SOURCE.split("def _sincronizar_contexto_item_venda", 1)[1].split("def _produtos_ativos_para_venda", 1)[0]
        self.assertIn("self.focus_get()", block)
        self.assertIn("winfo_ismapped", SOURCE)
        self.assertIn("setattr(self, nome, widget)", block)

    def test_every_product_entry_path_synchronizes_context(self):
        for method, next_method in [
            ("mostrar_lista_produtos_venda", "filtrar_produtos_venda"),
            ("filtrar_produtos_venda", "_preencher_sugestoes_produto"),
            ("navegar_sugestoes_produto", "confirmar_sugestao_produto"),
        ]:
            block = SOURCE.split(f"def {method}", 1)[1].split(f"def {next_method}", 1)[0]
            self.assertIn("_sincronizar_contexto_item_venda", block)

    def test_inline_selector_ghost_cannot_return(self):
        self.assertNotIn("def _criar_lista_produtos_inline", SOURCE)
        self.assertNotIn("_produto_sugestao_por_iid", SOURCE)

    def test_popup_does_not_require_entry_to_be_mapped_before_creation(self):
        display = SOURCE.split("def exibir_sugestoes_produto", 1)[1].split("def _cancelar_fechamento_sugestoes_produto", 1)[0]
        self.assertNotIn("winfo_ismapped()", display)
        self.assertIn("entry.winfo_toplevel()", display)
        self.assertIn("popup.deiconify()", display)

if __name__ == "__main__":
    unittest.main()
