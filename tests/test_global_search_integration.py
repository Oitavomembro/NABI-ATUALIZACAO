from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GlobalSearchIntegrationTests(unittest.TestCase):
    def test_ctrl_k_is_registered(self):
        source = (ROOT / "core" / "shortcut_manager.py").read_text(encoding="utf-8")
        self.assertIn('"<Control-k>"', source)
        self.assertIn('"<<NabiCommandPalette>>"', source)

    def test_application_opens_and_dispatches_palette(self):
        source = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn("def abrir_pesquisa_global", source)
        self.assertIn("def _executar_resultado_pesquisa_global", source)
        self.assertIn('self.bind("<<NabiCommandPalette>>"', source)

    def test_version_is_updated(self):
        version = (ROOT / "VERSAO.txt").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        source = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn("APP_VERSION = _ler_versao_aplicacao()", source)


if __name__ == "__main__":
    unittest.main()
