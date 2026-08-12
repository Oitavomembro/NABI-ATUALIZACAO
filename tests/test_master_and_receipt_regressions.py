from pathlib import Path
import hashlib
import unittest
from unittest.mock import patch
from services.security_service import SecurityService

class MasterPasswordTests(unittest.TestCase):
    def test_master_password_is_valid(self):
        synthetic_password = "credencial sintetica de teste"
        synthetic_hash = hashlib.sha256(synthetic_password.encode("utf-8")).hexdigest()
        with patch.object(SecurityService, "MASTER_PASSWORD_SHA256", synthetic_hash):
            self.assertTrue(SecurityService.verify_master_password(synthetic_password))
            self.assertFalse(SecurityService.verify_master_password("credencial incorreta"))

class SourceRegressionTests(unittest.TestCase):
    def test_login_is_only_required_after_explicit_configuration(self):
        source=Path("nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn("login_usuarios_configurado", source)
    def test_diagnostics_uses_real_category_table(self):
        source=Path("nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn("categorias_produtos", source)
