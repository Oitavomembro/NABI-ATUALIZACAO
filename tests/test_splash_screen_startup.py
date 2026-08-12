from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
SPLASH = (ROOT / "splash_screen.py").read_text(encoding="utf-8")
ENGINE = (ROOT / "splash_deep_trust_engine.py").read_text(encoding="utf-8")


class SplashScreenStartupTests(unittest.TestCase):
    def test_splash_runs_in_separate_process(self):
        self.assertIn("subprocess.Popen", MAIN)
        self.assertIn('"--splash-helper"', MAIN)
        self.assertIn("CREATE_NO_WINDOW", MAIN)

    def test_splash_has_deep_trust_lightspeed_and_brand(self):
        self.assertIn('BRAND = "NABICODE"', SPLASH)
        self.assertIn("class LightspeedSplash", SPLASH)
        self.assertIn("class WarpStar", ENGINE)
        self.assertIn("class NameStar", ENGINE)
        self.assertIn("NAME_IVORY = (255, 255, 255)", SPLASH)

    def test_main_closes_splash_before_revealing_app(self):
        self.assertIn("app.withdraw()", MAIN)
        self.assertIn("_stop_splash(stop_file)", MAIN)
        self.assertIn("splash_process.poll()", MAIN)
        self.assertIn("app.after_idle(reveal_application)", MAIN)
        self.assertIn("app.deiconify()", MAIN)

    def test_splash_is_lightweight_and_startup_only(self):
        self.assertIn("FPS = 60", SPLASH)
        self.assertIn("FRAME_MS = 16", SPLASH)
        self.assertIn("DURATION = 12.2", SPLASH)
        self.assertIn("self.clock.tick(self.engine.FPS)", SPLASH)
        self.assertIn("self.pygame.display.flip()", SPLASH)
        self.assertNotIn("time.sleep", SPLASH)
        self.assertIn("import splash_deep_trust_engine", SPLASH)
        self.assertNotIn("mostrar_tela", SPLASH)
        self.assertNotIn("abrir_pdv", SPLASH)

    def test_splash_supports_modal_pause_and_parent_liveness(self):
        self.assertIn('"--pause-file"', MAIN)
        self.assertIn('"--parent-pid"', MAIN)
        self.assertIn("self._set_window_visible(False)", SPLASH)
        self.assertIn("self._set_window_visible(True)", SPLASH)
        self.assertIn("_parent_is_alive", SPLASH)


if __name__ == "__main__":
    unittest.main()
