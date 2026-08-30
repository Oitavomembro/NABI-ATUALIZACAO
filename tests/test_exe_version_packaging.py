import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExeVersionPackagingTests(unittest.TestCase):
    def test_spec_bundles_version_file_using_absolute_project_path(self):
        source = (ROOT / "NabiCode.spec").read_text(encoding="utf-8")
        self.assertIn("version_file = os.path.join(project_root, 'VERSAO.txt')", source)
        self.assertIn("datas, binaries, hiddenimports = [(version_file, '.')]", source)

    def test_test_and_debug_builds_bundle_version_file(self):
        for filename in ("GERAR_EXE_TESTE.bat", "GERAR_EXE_DEBUG.bat"):
            with self.subTest(filename=filename):
                source = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn('--add-data "VERSAO.txt;."', source)

    def test_legacy_uses_compiled_fallback(self):
        source = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn('COMPILED_APP_VERSION = "2.5.2"', source)
        self.assertIn("return load_app_version(", source)
        self.assertNotIn('raise RuntimeError("VERSAO.txt', source)


if __name__ == "__main__":
    unittest.main()
