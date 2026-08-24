from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from assistant_nabi import AssistantTurn, ToolResult, UnavailableAssistantService

try:
    from PySide6.QtWidgets import QApplication, QMainWindow
    from ui_qt import app as qt_app
except (ImportError, OSError) as error:
    QT_AVAILABLE = False
    QT_ERROR = str(error)
else:
    QT_AVAILABLE = True
    QT_ERROR = ""


class FakeWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.docks = []
        self.product_search_terms = []
        self.module_hub_calls = 0

    def addDockWidget(self, area, dock):
        self.docks.append((area, dock))

    def load_assistant_draft(self, draft, authorization=None):
        return None

    def open_assistant_product_search(self, term=""):
        self.product_search_terms.append(term)
        return True

    def open_administrative_hub(self):
        self.module_hub_calls += 1


@unittest.skipUnless(QT_AVAILABLE, f"Qt indisponível: {QT_ERROR}")
class QtApplicationAssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_sem_servico_preserva_shell_sem_painel(self):
        with (
            patch.object(qt_app, "PDVWindow", FakeWindow),
            patch.object(qt_app, "PDVViewModel", lambda application: application),
        ):
            _, window = qt_app.create_application(object(), [])
        self.assertEqual(window.docks, [])
        self.assertFalse(hasattr(window, "nabi_assistant_dock"))

    def test_servico_indisponivel_cria_painel_lateral_em_falha_fechada(self):
        service = UnavailableAssistantService("Modelo ausente.")
        with (
            patch.object(qt_app, "PDVWindow", FakeWindow),
            patch.object(qt_app, "PDVViewModel", lambda application: application),
        ):
            _, window = qt_app.create_application(
                object(), [], assistant_service=service
            )
        self.assertEqual(len(window.docks), 1)
        panel = window.nabi_assistant_dock.widget()
        self.assertFalse(panel.send.isEnabled())
        self.assertIn("Modelo ausente", panel.history.toPlainText())
        window.close()

    def test_gerenciador_de_ativacao_chega_ao_painel_sem_ativar_sozinho(self):
        service = UnavailableAssistantService("Autenticação necessária.")
        activation = object()
        with (
            patch.object(qt_app, "PDVWindow", FakeWindow),
            patch.object(qt_app, "PDVViewModel", lambda application: application),
        ):
            _, window = qt_app.create_application(
                object(), [], assistant_service=service,
                assistant_activation=activation,
            )
        panel = window.nabi_assistant_dock.widget()
        self.assertIs(panel._activation_manager, activation)
        self.assertFalse(panel.send.isEnabled())
        window.close()

    def test_servico_de_revisao_xml_chega_ao_painel_sem_importar(self):
        service = UnavailableAssistantService("Autenticação necessária.")
        nfe_entry = object()
        with (
            patch.object(qt_app, "PDVWindow", FakeWindow),
            patch.object(qt_app, "PDVViewModel", lambda application: application),
        ):
            _, window = qt_app.create_application(
                object(), [], assistant_service=service,
                nfe_entry_service=nfe_entry,
            )
        panel = window.nabi_assistant_dock.widget()
        self.assertIs(panel._nfe_entry_service, nfe_entry)
        self.assertFalse(panel.prepare_nfe_entry_button.isHidden())
        self.assertFalse(panel.prepare_nfe_entry_button.isEnabled())
        window.close()

    def test_intencao_da_nabi_chega_a_porta_explicita_do_pdv(self):
        class Service:
            available = True

        with (
            patch.object(qt_app, "PDVWindow", FakeWindow),
            patch.object(qt_app, "PDVViewModel", lambda application: application),
        ):
            _, window = qt_app.create_application(
                object(), [], assistant_service=Service()
            )
        panel = window.nabi_assistant_dock.widget()
        panel._generation = 7
        panel._complete(7, AssistantTurn("Abrindo pesquisa.", (ToolResult(
            "request-1",
            "interface.abrir_pesquisa_produtos",
            True,
            {"action": "OPEN_PRODUCT_SEARCH", "term": "café"},
        ),)))
        self.assertEqual(window.product_search_terms, ["café"])
        window.close()

    def test_intencao_da_nabi_abre_apenas_a_central_de_modulos(self):
        class Service:
            available = True

        with (
            patch.object(qt_app, "PDVWindow", FakeWindow),
            patch.object(qt_app, "PDVViewModel", lambda application: application),
        ):
            _, window = qt_app.create_application(
                object(), [], assistant_service=Service(),
            )
        panel = window.nabi_assistant_dock.widget()
        panel._generation = 8
        panel._complete(8, AssistantTurn("Abrindo módulos.", (ToolResult(
            "request-2", "interface.abrir_modulos", True,
            {"action": "OPEN_MODULE_HUB"},
        ),)))
        self.assertEqual(window.module_hub_calls, 1)
        window.close()


if __name__ == "__main__":
    unittest.main()
