from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main_qt


class MainQtAssistantActivationTests(unittest.TestCase):
    def test_composicao_nao_inicia_modelo_antes_da_autenticacao(self):
        database = SimpleNamespace(connect=Mock())
        profile = SimpleNamespace(app_dir=Path("C:/NabiCode/Teste"))
        container = SimpleNamespace(query=object())
        security = Mock()
        security.authenticate.return_value = object()
        system = Mock()
        system.get_config.return_value = "hash-legado"
        runtime = Mock()
        runtime.create_model_adapter.return_value = "modelo"

        with (
            patch.object(main_qt, "SystemRepository", return_value=system),
            patch.object(main_qt, "SecurityService", return_value=security),
            patch.object(main_qt, "AdminAuditService", return_value="auditoria"),
            patch.object(main_qt, "LocalLlamaServer", return_value=runtime) as runtime_cls,
            patch.object(
                main_qt, "create_draft_assistant", return_value="assistente"
            ) as assistant_factory,
        ):
            activation = main_qt._create_assistant_activation(
                database, profile, container
            )
            runtime_cls.assert_not_called()
            runtime.start.assert_not_called()
            self.assertEqual(
                activation.activate("operador", "senha-real"), "assistente"
            )

        security.bootstrap_admin.assert_called_once_with("hash-legado")
        security.authenticate.assert_called_once_with("operador", "senha-real")
        runtime.start.assert_called_once_with()
        assistant_factory.assert_called_once()
        call = runtime_cls.call_args.kwargs
        self.assertEqual(call["model_directory"], Path("C:/NabiCode/Teste/ia/models"))
        self.assertEqual(
            call["runtime_directory"], Path("C:/NabiCode/Teste/ia/runtime/b10537")
        )


if __name__ == "__main__":
    unittest.main()
