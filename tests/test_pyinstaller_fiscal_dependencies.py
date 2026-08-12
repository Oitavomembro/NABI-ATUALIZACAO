from pathlib import Path
import unittest


class PyInstallerFiscalDependenciesTests(unittest.TestCase):
    def test_spec_includes_cryptography_runtime_modules(self):
        spec = (Path(__file__).resolve().parents[1] / "NabiCode.spec").read_text(encoding="utf-8")
        required = (
            "collect_submodules",
            "collect_dynamic_libs",
            "cryptography.hazmat.primitives.serialization.pkcs12",
            "cryptography.hazmat.bindings._rust",
            "lxml.etree",
            "requests.adapters",
        )
        for item in required:
            self.assertIn(item, spec)

    def test_fiscal_imports_are_optional_for_non_fiscal_startup(self):
        source = (Path(__file__).resolve().parents[1] / "services" / "fiscal_service.py").read_text(encoding="utf-8")
        self.assertIn("except ModuleNotFoundError:  # Não deve impedir o uso não fiscal", source)
        self.assertIn('self._require_dependency("cryptography")', source)


if __name__ == "__main__":
    unittest.main()
