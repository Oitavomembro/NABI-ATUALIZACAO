from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class UniversalLayoutIntegrationTests(unittest.TestCase):
    def test_product_form_uses_required_tabs_and_fixed_footer(self):
        start = SOURCE.index("    def abrir_cadastro_produto")
        end = SOURCE.index("    def editar_produto_selecionado", start)
        block = SOURCE[start:end]
        for tab in ("Geral", "Preços", "Estoque", "Fiscal"):
            self.assertIn(f'abas_produto.add("{tab}")', block)
        self.assertIn("BidirectionalScrollableFrame", block)
        self.assertIn("rodape = ctk.CTkFrame(win", block)
        self.assertIn("UniversalLayoutPolicy.safe_minsize", block)

    def test_xml_import_uses_universal_responsive_policy(self):
        start = SOURCE.index("    def abrir_importacao_xml")
        end = SOURCE.index("    def abrir_pdv_independente", start)
        block = SOURCE[start:end]
        self.assertIn("UniversalLayoutPolicy.metrics", block)
        self.assertIn("UniversalLayoutPolicy.safe_minsize", block)
        self.assertIn("scroll_x = ttk.Scrollbar", block)
        self.assertIn("rodape = ctk.CTkFrame(win", block)

    def test_finance_screen_uses_persistent_header_scroll_and_footer(self):
        start = SOURCE.index("    def tela_financeiro")
        end = SOURCE.index("    def carregar_financeiro", start)
        block = SOURCE[start:end]
        self.assertNotIn("self.criar_cabecalho_e_botoes(frame)", block)
        self.assertEqual(SOURCE.count("self.criar_cabecalho_e_botoes("), 1)
        self.assertIn("self.adicionar_rodape_status(frame)", block)
        self.assertIn("BidirectionalScrollableFrame", block)
        self.assertIn('orient="horizontal"', block)
        self.assertIn('orient="vertical"', block)


if __name__ == "__main__":
    unittest.main()
