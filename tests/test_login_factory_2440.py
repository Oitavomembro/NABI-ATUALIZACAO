from pathlib import Path
import hashlib
import unittest
from unittest.mock import patch

from services.security_service import SecurityService


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class LoginFactory2440Tests(unittest.TestCase):
    def test_master_password_normalizes_case_and_spaces(self):
        normalized = "credencial sintetica de teste"
        synthetic_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        with patch.object(SecurityService, "MASTER_PASSWORD_SHA256", synthetic_hash):
            self.assertTrue(SecurityService.verify_master_password(normalized))
            self.assertTrue(SecurityService.verify_master_password("  CREDENCIAL   SINTETICA   DE   TESTE  "))
            self.assertFalse(SecurityService.verify_master_password("credencial incorreta"))

    def test_startup_novo_exige_configuracao_e_login_real(self):
        self.assertIn("def _login_usuarios_habilitado(self):", SOURCE)
        self.assertIn('obter_config("configuracao_inicial_concluida_v1")', SOURCE)
        self.assertIn("def _executar_configuracao_inicial(self):", SOURCE)
        self.assertIn("self.security.start_session_without_password(\"admin\")", SOURCE)
        self.assertIn("def abrir_login_usuario(self, inicial=False):", SOURCE)
        self.assertIn("self.security.authenticate(usuario.get(), senha.get())", SOURCE)
        setup = SOURCE.index("if primeira_vez:\n            with startup_modal_scope():\n                if not self._executar_configuracao_inicial()")
        modules = SOURCE.index("self.criar_menu_lateral()")
        worker = SOURCE.index("self.after_idle(self._iniciar_worker_fiscal)")
        self.assertLess(setup, modules)
        self.assertLess(setup, worker)

    def test_factory_reset_clears_login_consent(self):
        self.assertIn('"login_inicio_ativado_pelo_usuario_v2442": "0"', SOURCE)


if __name__ == "__main__":
    unittest.main()
