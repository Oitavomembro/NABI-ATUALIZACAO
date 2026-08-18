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

    def test_build_oficial_inclui_schemas_fiscais(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / "build_tools" / "pyinstaller" / "nabicode.spec").read_text(encoding="utf-8")
        self.assertIn('"resources" / "fiscal" / "schemas"', spec)
        self.assertTrue((root / "resources/fiscal/schemas/nfe_010e_v1.02/nfe_v4.00.xsd").is_file())
        self.assertTrue((root / "resources/fiscal/schemas/eventos_010d_v1.03/envEvento_v1.00.xsd").is_file())


if __name__ == "__main__":
    unittest.main()
