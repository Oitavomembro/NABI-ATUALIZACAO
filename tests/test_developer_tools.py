from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from services.developer_tools import DeveloperToolsService


class DeveloperToolsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "VERSAO.txt").write_text("2.4.32\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "CHANGELOG.md").write_text("teste", encoding="utf-8")
        self.service = DeveloperToolsService(self.root, self.root / "banco.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_version_comes_from_version_file(self):
        self.assertEqual(self.service.version, "2.4.32")

    def test_update_comparison(self):
        latest = self.root / "latest.txt"
        latest.write_text("2.5.0", encoding="utf-8")
        result = self.service.check_update(latest)
        self.assertTrue(result["update_available"])

    def test_clean_build_removes_generated_directories(self):
        (self.root / "build").mkdir()
        cache = self.root / "pkg" / "__pycache__"
        cache.mkdir(parents=True)
        removed = self.service.clean_build()
        self.assertFalse((self.root / "build").exists())
        self.assertFalse(cache.exists())
        self.assertEqual(len(removed), 2)

    def test_export_diagnostic_creates_valid_zip(self):
        archive = self.service.export_diagnostic(self.root / "exports")
        self.assertTrue(archive.is_file())
        with zipfile.ZipFile(archive) as package:
            self.assertIn("manifest.json", package.namelist())
            self.assertIn("VERSAO.txt", package.namelist())

    def test_validate_tooling_reports_missing_files(self):
        result = self.service.validate_tooling()
        self.assertFalse(result["ok"])
        self.assertIn("main.py", result["missing"])

    def test_validate_tooling_accepts_complete_minimal_project(self):
        for name in self.service.REQUIRED_PROJECT_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == "VERSAO.txt":
                continue
            content = "('VERSAO.txt', '.')" if name == "NabiCode.spec" else "arquivo"
            path.write_text(content, encoding="utf-8")
        tests = self.root / "tests"
        tests.mkdir(exist_ok=True)
        (tests / "test_sample.py").write_text("import unittest\n", encoding="utf-8")
        result = self.service.validate_tooling()
        self.assertTrue(result["ok"], result)

    def test_run_tests_refuses_invalid_tooling(self):
        result = self.service.run_tests()
        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 2)



if __name__ == "__main__":
    unittest.main()
