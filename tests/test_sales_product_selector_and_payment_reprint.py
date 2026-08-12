from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class SalesProductSelectorAndPaymentReprintTests(unittest.TestCase):
    def test_sales_has_explicit_product_dropdown_button(self):
        self.assertGreaterEqual(
            SOURCE.count("command=self.mostrar_lista_produtos_venda"), 2
        )
        self.assertIn('text="▼"', SOURCE)

    def test_down_arrow_lists_products_even_with_empty_search(self):
        start = SOURCE.index("    def navegar_sugestoes_produto")
        end = SOURCE.index("    def confirmar_sugestao_produto", start)
        block = SOURCE[start:end]
        self.assertIn("self.mostrar_lista_produtos_venda()", block)

    def test_product_selector_uses_stable_native_popup(self):
        display_start = SOURCE.index("    def exibir_sugestoes_produto")
        display_end = SOURCE.index("    def _cancelar_fechamento_sugestoes_produto", display_start)
        display_block = SOURCE[display_start:display_end]
        self.assertNotIn("def _criar_lista_produtos_inline", SOURCE)
        self.assertIn("tk.Toplevel", display_block)
        self.assertIn("ttk.Treeview", display_block)
        self.assertIn("_produto_sugestao_por_indice", display_block)
        self.assertIn("popup.withdraw()", display_block)
        self.assertIn("popup.deiconify()", display_block)


    def test_payment_reprint_does_not_generate_pdf_automatically(self):
        start = SOURCE.index("    def reimprimir_movimentacao")
        end = SOURCE.index("    def disparar_edicao_dash", start)
        block = SOURCE[start:end]
        payment_branch = block.split('elif tipo == "PAGAMENTO":', 1)[1].split("else:", 1)[0]
        self.assertIn("janela_recibo_pagamento_cliente", payment_branch)
        self.assertNotIn("gerar_pdf_movimentacao", payment_branch)


if __name__ == "__main__":
    unittest.main()
