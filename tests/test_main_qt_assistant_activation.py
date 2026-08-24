from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main_qt
from licensing.gate import Capability


class MainQtAssistantActivationTests(unittest.TestCase):
    @staticmethod
    def gate(*allowed):
        gate = Mock()
        gate.allows.side_effect = lambda capability: capability in allowed
        return gate

    def test_licenca_sem_assistente_nao_compoe_nabi_nem_nfe(self):
        database = object()
        profile = object()
        container = object()
        gate = self.gate(Capability.QT, Capability.FISCAL_WRITE)
        with (
            patch.object(main_qt, "NFeImportRepository") as repository,
            patch.object(main_qt, "NFeImportService") as importer,
            patch.object(main_qt, "NFeEntryDraftService") as drafts,
            patch.object(main_qt, "_create_assistant_activation") as activation,
        ):
            result = main_qt._create_licensed_assistant(
                database, profile, container, gate
            )
        self.assertEqual(result, (None, None, None))
        repository.assert_not_called()
        importer.assert_not_called()
        drafts.assert_not_called()
        activation.assert_not_called()

    def test_assistente_sem_fiscal_nao_compoe_importacao_nfe(self):
        gate = self.gate(Capability.QT, Capability.ASSISTANT)
        with (
            patch.object(main_qt, "NFeImportRepository") as repository,
            patch.object(main_qt, "NFeImportService") as importer,
            patch.object(main_qt, "NFeEntryDraftService") as drafts,
            patch.object(
                main_qt, "_create_assistant_activation", return_value="ativação"
            ) as activation,
        ):
            service, actual_activation, nfe = main_qt._create_licensed_assistant(
                "banco", "perfil", "container", gate
            )
        self.assertIsInstance(service, main_qt.UnavailableAssistantService)
        self.assertEqual(actual_activation, "ativação")
        self.assertIsNone(nfe)
        activation.assert_called_once_with(
            "banco", "perfil", "container", None, None
        )
        repository.assert_not_called()
        importer.assert_not_called()
        drafts.assert_not_called()

    def test_assistente_com_fiscal_compoe_revisao_nfe_sem_sefaz(self):
        gate = self.gate(
            Capability.QT, Capability.ASSISTANT, Capability.FISCAL_WRITE
        )
        with (
            patch.object(main_qt, "NFeImportRepository", return_value="repo") as repository,
            patch.object(main_qt, "NFeImportService", return_value="importador") as importer,
            patch.object(main_qt, "NFeEntryDraftService", return_value="rascunho") as drafts,
            patch.object(
                main_qt, "_create_assistant_activation", return_value="ativação"
            ) as activation,
        ):
            _service, _actual_activation, nfe = main_qt._create_licensed_assistant(
                "banco", "perfil", "container", gate
            )
        self.assertEqual(nfe, "rascunho")
        repository.assert_called_once_with("banco")
        importer.assert_called_once_with("repo")
        drafts.assert_called_once_with("importador")
        activation.assert_called_once_with(
            "banco", "perfil", "container", "rascunho", "importador"
        )

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

    def test_composicao_injeta_compras_somente_quando_backend_oficial_existe(self):
        database = SimpleNamespace(connect=Mock())
        profile = SimpleNamespace(app_dir=Path("C:/NabiCode/Teste"))
        purchase = object()
        financial_query = object()
        container = SimpleNamespace(
            query=object(), purchase_service=purchase, financial_query=financial_query
        )
        security = Mock()
        security.authenticate.return_value = object()
        system = Mock()
        system.get_config.return_value = "hash"
        runtime = Mock()
        runtime.create_model_adapter.return_value = "modelo"
        with (
            patch.object(main_qt, "SystemRepository", return_value=system),
            patch.object(main_qt, "SecurityService", return_value=security),
            patch.object(main_qt, "AdminAuditService", return_value="auditoria"),
            patch.object(main_qt, "LocalLlamaServer", return_value=runtime),
            patch.object(
                main_qt, "create_purchase_assistant_components",
                return_value=("rascunhos-compra", "executor-compra"),
            ) as purchase_factory,
            patch.object(
                main_qt, "PurchaseManagementService",
                return_value="consultas-compra",
            ),
            patch.object(main_qt, "create_draft_assistant", return_value="assistente") as factory,
        ):
            activation = main_qt._create_assistant_activation(database, profile, container)
            activation.activate("op", "senha")
        purchase_factory.assert_called_once_with(container)
        self.assertEqual(factory.call_args.kwargs["purchase_draft_service"], "rascunhos-compra")
        self.assertEqual(factory.call_args.kwargs["purchase_executor"], "executor-compra")
        self.assertEqual(factory.call_args.kwargs["purchase_query_service"], "consultas-compra")
        self.assertIs(factory.call_args.kwargs["financial_query_service"], financial_query)

    def test_composicao_injeta_entrada_nfe_sem_iniciar_runtime_ou_sefaz(self):
        database = SimpleNamespace(connect=Mock())
        profile = SimpleNamespace(app_dir=Path("C:/NabiCode/Teste"))
        container = SimpleNamespace(query=object())
        drafts = object()
        imports = object()
        security = Mock()
        security.authenticate.return_value = object()
        runtime = Mock()
        runtime.create_model_adapter.return_value = "modelo"
        with (
            patch.object(main_qt, "SystemRepository") as system_cls,
            patch.object(main_qt, "SecurityService", return_value=security),
            patch.object(main_qt, "AdminAuditService", return_value="auditoria"),
            patch.object(main_qt, "LocalLlamaServer", return_value=runtime),
            patch.object(main_qt, "NabiCodeNFeEntryAssistantGateway", return_value="executor-nfe") as gateway,
            patch.object(main_qt, "create_draft_assistant", return_value="assistente") as factory,
        ):
            system_cls.return_value.get_config.return_value = "hash"
            activation = main_qt._create_assistant_activation(
                database, profile, container, drafts, imports
            )
            runtime.start.assert_not_called()
            activation.activate("op", "senha")
        gateway.assert_called_once_with(drafts, imports)
        self.assertIs(factory.call_args.kwargs["nfe_entry_draft_service"], drafts)
        self.assertEqual(factory.call_args.kwargs["nfe_entry_executor"], "executor-nfe")


if __name__ == "__main__":
    unittest.main()
