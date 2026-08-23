from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from assistant_nabi import UnavailableAssistantService

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

    def addDockWidget(self, area, dock):
        self.docks.append((area, dock))


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


if __name__ == "__main__":
    unittest.main()
