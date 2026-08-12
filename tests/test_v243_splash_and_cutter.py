from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPLASH = (ROOT / "splash_screen.py").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
PRINTING = (ROOT / "services" / "printing_service.py").read_text(encoding="utf-8")
UI = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
SCHEMA = (ROOT / "database" / "schema_initializer.py").read_text(encoding="utf-8")

class V243SplashAndCutterTests(unittest.TestCase):
    def test_splash_reuses_display_surface_and_keeps_controlled_fade(self):
        self.assertEqual(SPLASH.count("self.pygame.display.set_mode("), 1)
        self.assertIn("self.screen.fill(self.engine.SPACE)", SPLASH)
        self.assertIn("self.pygame.display.flip()", SPLASH)
        self.assertIn("fade_out = 1.0 - smooth((elapsed - 11.0) / 1.2)", SPLASH)
        self.assertNotIn("tkinter", SPLASH)

    def test_main_reveals_ready_window_without_alpha_animation(self):
        self.assertIn('app.attributes("-alpha", 1.0)', MAIN)
        self.assertIn("app.deiconify()", MAIN)
        self.assertNotIn("fade_main_in", MAIN)
        self.assertNotIn('app.attributes("-alpha", 0.0)', MAIN)
        self.assertIn("_stop_splash(stop_file)", MAIN)

    def test_raw_print_appends_escpos_cut(self):
        self.assertIn("def _cut_payload", PRINTING)
        self.assertIn('b"\\x1d\\x56\\x00"', PRINTING)
        self.assertIn('b"\\x1d\\x56\\x01"', PRINTING)
        self.assertIn("def _raw_payload", PRINTING)
        self.assertIn("return body + self._cut_payload()", PRINTING)
        self.assertIn("win32print.WritePrinter(handle, self._raw_payload(text))", PRINTING)

    def test_cutter_is_configurable(self):
        self.assertIn("Corte automático da impressora térmica", UI)
        self.assertIn("impressao_corte_automatico", UI)
        self.assertIn('("impressao_corte_automatico", "1")', SCHEMA)
        self.assertNotIn('("impressao_corte_automatico", "0")', SCHEMA)
        self.assertIn('migracao_corte_automatico_2494', SCHEMA)

if __name__ == "__main__":
    unittest.main()
