from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")

class Sprint135PDVRegressionTests(unittest.TestCase):
    def test_product_list_uses_external_native_popup(self):
        display = SOURCE.split("def exibir_sugestoes_produto", 1)[1].split("def _cancelar_fechamento_sugestoes_produto", 1)[0]
        self.assertNotIn("def _criar_lista_produtos_inline", SOURCE)
        self.assertIn("tk.Toplevel", display)
        self.assertIn("ttk.Treeview", display)
        self.assertIn("_produto_sugestao_por_indice", display)
        self.assertIn("entry.winfo_toplevel()", display)


    def test_product_arrow_loads_active_products(self):
        block = SOURCE.split("def mostrar_lista_produtos_venda", 1)[1].split("def filtrar_produtos_venda", 1)[0]
        self.assertIn("_produtos_ativos_para_venda", block)
        self.assertIn("_preencher_sugestoes_produto", block)

    def test_barcode_selector_exists_and_sets_price(self):
        block = SOURCE.split("def _selecionar_produto_por_codigo_barras", 1)[1].split("def adicionar_item_carrinho", 1)[0]
        self.assertIn("codigo_barras", block)
        self.assertIn("produto_venda_selecionado_id", block)
        self.assertIn("MoneyEntryBehavior.set_value(self.entry_valor_venda, preco)", block)

    def test_sale_always_asks_before_printing_or_generating_pdf(self):
        block = SOURCE.split("def finalizar_venda", 1)[1].split("def tela_clientes", 1)[0]
        self.assertIn("janela_venda_finalizada", block)
        self.assertNotIn("emitir_venda_conforme_perfil(", block)
        self.assertNotIn("gerar_pdf_venda", block)

    def test_native_three_way_confirmation_controls_receipt_output(self):
        block = SOURCE.split("def janela_venda_finalizada", 1)[1].split("def emitir_venda_conforme_perfil", 1)[0]
        self.assertNotIn("messagebox.askyesnocancel", block)
        self.assertIn("CTkToplevel", block)
        self.assertIn("SIM — imprimir cupom 80 mm", block)
        self.assertIn("Finalizar", block)
        self.assertIn("Gerar PDF", block)
        self.assertIn("imprimir_cupom_venda_80mm", block)
        self.assertIn("gerar_pdf_venda", block)
        self.assertIn("_abrir_arquivo_sistema", block)

    def test_pdf_is_generated_only_by_explicit_choice_or_pdf_virtual_profile(self):
        block = SOURCE.split("def emitir_venda_conforme_perfil", 1)[1].split("def janela_recibo_pagamento_cliente", 1)[0]
        self.assertIn('if perfil == "PDF virtual"', block)
        self.assertIn('if perfil == "Cupom 80 mm"', block)
        self.assertIn("imprimir_texto_windows", block)

if __name__ == "__main__":
    unittest.main()
