import tempfile
import unittest
from pathlib import Path

from core.app_version import load_app_version, normalize_app_version, version_file_candidates


class AppVersionTests(unittest.TestCase):
    def test_normalize_accepts_bom_and_v_prefix(self):
        self.assertEqual(normalize_app_version("\ufeff v2.4.73\n"), "2.4.73")

    def test_missing_file_uses_compiled_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = load_app_version(
                "2.4.73",
                source_file=root / "missing" / "nabicode_legacy.py",
                executable=root / "dist" / "NabiCode.exe",
                runtime_dir=root / "_MEI_missing",
                explicit_path=root / "missing_version.txt",
            )
        self.assertEqual(result, "2.4.73")

    def test_runtime_meipass_file_has_priority_over_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "_MEI123"
            runtime.mkdir()
            (runtime / "VERSAO.txt").write_text("\ufeff2.4.99\n", encoding="utf-8")
            result = load_app_version(
                "2.4.73",
                source_file=root / "src" / "nabicode_legacy.py",
                executable=root / "dist" / "NabiCode.exe",
                runtime_dir=runtime,
            )
        self.assertEqual(result, "2.4.99")

    def test_invalid_runtime_file_does_not_abort_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "_MEI123"
            runtime.mkdir()
            (runtime / "VERSAO.txt").write_text("versao-quebrada", encoding="utf-8")
            result = load_app_version(
                "2.4.73",
                source_file=root / "src" / "nabicode_legacy.py",
                executable=root / "dist" / "NabiCode.exe",
                runtime_dir=runtime,
            )
        self.assertEqual(result, "2.4.73")

    def test_candidates_include_executable_and_runtime_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = version_file_candidates(
                source_file=root / "src" / "nabicode_legacy.py",
                executable=root / "dist" / "NabiCode.exe",
                runtime_dir=root / "_MEI123",
            )
        self.assertIn((root / "dist" / "VERSAO.txt").resolve(), candidates)
        self.assertIn((root / "_MEI123" / "VERSAO.txt").resolve(), candidates)


if __name__ == "__main__":
    unittest.main()
