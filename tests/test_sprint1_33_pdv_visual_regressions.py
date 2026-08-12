from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
SPLASH = (ROOT / "splash_screen.py").read_text(encoding="utf-8")

class Sprint133VisualRegressionTests(unittest.TestCase):
    def test_post_sale_opens_pdf_without_custom_modal(self):
        block = LEGACY.split("def janela_pos_venda_comprovante", 1)[1].split("def cancelar_venda_pdv", 1)[0]
        self.assertIn("os.path.getsize", block)
        self.assertIn("_abrir_arquivo_sistema(caminho_pdf)", block)
        self.assertNotIn("Toplevel", block)
        self.assertNotIn("wait_window", block)

    def test_product_popup_is_compact_and_stable(self):
        display = LEGACY.split("def exibir_sugestoes_produto", 1)[1].split("def _cancelar_fechamento_sugestoes_produto", 1)[0]
        self.assertIn("tk.Toplevel", display)
        self.assertIn("ttk.Treeview", display)
        self.assertIn("min(10, len(sugestoes))", display)
        self.assertIn('background=[("selected", "#8957e5")]', display)


    def test_dashboard_does_not_hide_columns_with_horizontal_scroll(self):
        block = LEGACY.split("Histórico de Movimentações do Dia", 1)[1].split("return frame", 1)[0]
        self.assertNotIn("dash_scroll_x", block)
        self.assertNotIn("xscrollcommand", block)
        self.assertIn('self.tabela_dash.column("Descrição", width=320', block)

    def test_splash_preserves_canonical_1280x720_ratio(self):
        self.assertIn("LOGICAL_WIDTH = 1280", SPLASH)
        self.assertIn("LOGICAL_HEIGHT = 720", SPLASH)
        self.assertIn("(self.engine.W, self.engine.H)", SPLASH)
        self.assertIn("self.display_width = self.engine.W", SPLASH)
        self.assertIn("self.display_height = self.engine.H", SPLASH)
        self.assertNotIn("screen_width * 0.68", SPLASH)
        self.assertIn("FRAME_MS = 16", SPLASH)
        self.assertIn("STAR_COUNT = 2050", SPLASH)

if __name__ == "__main__":
    unittest.main()
