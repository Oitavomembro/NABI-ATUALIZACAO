from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.diagnostic_logging import SafeRotatingFileHandler, configure_diagnostic_logging


class DiagnosticLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temp.name) / "nabicode.log"
        self.logger = logging.getLogger(f"NabiCode.Test.{id(self)}")
        self.logger.handlers.clear()
        self.logger.propagate = False
        self.handler = configure_diagnostic_logging(
            self.logger,
            self.log_file,
            app_version="2.5.0",
            runtime_profile="TESTE",
            max_bytes=4096,
            backup_count=2,
        )

    def tearDown(self) -> None:
        self.handler.close()
        self.logger.handlers.clear()
        self.temp.cleanup()

    def test_error_preserves_traceback_and_context(self) -> None:
        try:
            raise ValueError("falha controlada")
        except ValueError:
            self.logger.exception("operaÃ§Ã£o de teste")
        content = self.log_file.read_text(encoding="utf-8")
        self.assertIn("ValueError: falha controlada", content)
        self.assertIn("versao=2.5.0", content)
        self.assertIn("perfil=TESTE", content)

    def test_sensitive_values_are_redacted_from_message_and_exception(self) -> None:
        try:
            raise RuntimeError("token=segredo-total")
        except RuntimeError:
            self.logger.exception("senha: MinhaSenha password=OutraSenha")
        content = self.log_file.read_text(encoding="utf-8")
        self.assertNotIn("segredo-total", content)
        self.assertNotIn("MinhaSenha", content)
        self.assertNotIn("OutraSenha", content)
        self.assertIn("<omitido>", content)

    def test_logging_write_failure_does_not_escape(self) -> None:
        with patch.object(SafeRotatingFileHandler, "shouldRollover", side_effect=OSError("disco bloqueado")):
            self.logger.error("falha externa")
