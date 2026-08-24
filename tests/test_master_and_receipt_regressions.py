from pathlib import Path
import unittest
from services.security_service import SecurityService

class MasterPasswordTests(unittest.TestCase):
    def test_master_password_was_removed(self):
        self.assertFalse(hasattr(SecurityService, "MASTER_PASSWORD_SHA256"))
        self.assertFalse(hasattr(SecurityService, "verify_master_password"))

class SourceRegressionTests(unittest.TestCase):
    def test_login_is_only_required_after_explicit_configuration(self):
        source=Path("nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn("login_usuarios_configurado", source)
    def test_diagnostics_uses_real_category_table(self):
        source=Path("nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn("categorias_produtos", source)
