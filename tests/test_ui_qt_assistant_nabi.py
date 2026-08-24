from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from assistant_nabi import AssistantTurn, ToolResult
from commercial.application.pdv_session import PDVSession

try:
    from PySide6.QtWidgets import QApplication, QDockWidget
    from ui_qt.assistant_nabi import NabiAssistantPanel
    from ui_qt.app import create_application
except (ImportError, OSError) as error:
    QT_AVAILABLE = False
    QT_ERROR = str(error)
else:
    QT_AVAILABLE = True
    QT_ERROR = ""


class Service:
    def ask(self, message):
        return AssistantTurn(f"Resposta para {message}")


@unittest.skipUnless(QT_AVAILABLE, f"Qt indisponível: {QT_ERROR}")
class NabiAssistantPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = NabiAssistantPanel(Service())
        self.panel.show()
        QApplication.processEvents()

    def tearDown(self):
        self.panel.close()

    def test_texto_vazio_nao_dispara_e_voz_permanece_desativada(self):
        generation = self.panel._generation
        self.panel.submit()
        self.assertEqual(self.panel._generation, generation)
        self.assertFalse(self.panel.voice.isEnabled())
        self.assertIn("Digite", self.panel.status.text())

    def test_resultado_e_renderizado_sem_html_injetado(self):
        turn = AssistantTurn(
            "<script>não executar</script>",
            (ToolResult("r1", "produtos.pesquisar", True, {}),),
        )
        self.panel._generation = 4
        self.panel._busy = True
        self.panel._complete(4, turn)
        html = self.panel.history.toHtml()
        self.assertNotIn("<script>", html)
        self.assertIn("não executar", self.panel.history.toPlainText())
        self.assertIn("Concluído", self.panel.status.text())

    def test_parar_invalida_resposta_atrasada_e_bloqueia_novos_comandos(self):
        self.panel._generation = 10
        self.panel.stop_nabi()
        self.assertFalse(self.panel.send.isEnabled())
        before = self.panel.history.toPlainText()
        self.panel._complete(10, AssistantTurn("resposta atrasada"))
        self.assertEqual(self.panel.history.toPlainText(), before)
        self.panel.reactivate()
        self.assertTrue(self.panel.send.isEnabled())
        self.assertEqual(self.panel.status.text(), "Disponível")

    def test_falha_segura_aparece_como_bloqueada(self):
        self.panel._generation = 2
        self.panel._complete(2, AssistantTurn("Modelo indisponível", safe_failure=True))
        self.assertEqual(self.panel.status.text(), "Bloqueada")

    def test_renderiza_produtos_deterministicamente_e_escapa_dados(self):
        turn = AssistantTurn("Consulta concluída", (ToolResult(
            "r2", "produtos.pesquisar", True,
            {"items": [{
                "product_id": 1, "code": "P1", "description": "<b>Café</b>",
                "sale_price": "12.50", "active": True,
            }]},
        ),))
        self.panel._generation = 3
        self.panel._complete(3, turn)
        plain = self.panel.history.toPlainText()
        self.assertIn("P1 — <b>Café</b> — R$ 12.50", plain)
        self.assertNotIn("<b>Café</b>", self.panel.history.toHtml())

    def test_renderiza_cliente_sem_expor_campos_sensiveis(self):
        result = ToolResult("r3", "clientes.pesquisar", True, {
            "items": [{
                "customer_id": 9, "code": "C9", "record_number": 91, "name": "Maria"
            }]
        })
        text = self.panel._result_text(result)
        self.assertEqual(text, "91 — Maria")
        for field in ("cpf", "telefone", "endereço"):
            self.assertNotIn(field, text.casefold())


@unittest.skipUnless(QT_AVAILABLE, f"Qt indisponível: {QT_ERROR}")
class NabiAssistantShellIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_startup_padrao_nao_cria_nem_tenta_criar_painel(self):
        called = []

        class Application:
            new_session = staticmethod(PDVSession)

        _qt, window = create_application(Application(), argv=[])
        try:
            self.assertEqual(window.findChildren(QDockWidget, "nabiAssistantDock"), [])
            self.assertFalse(hasattr(window, "nabi_assistant_dock"))
            self.assertEqual(called, [])
        finally:
            window.close()

    def test_opt_in_cria_painel_lateral_removivel_com_servico_fornecido(self):
        class Application:
            new_session = staticmethod(PDVSession)

        service = Service()
        calls = []

        def factory(parent):
            calls.append(parent)
            return NabiAssistantPanel(service, parent)

        _qt, window = create_application(
            Application(), argv=[], assistant_panel_factory=factory
        )
        try:
            dock = window.nabi_assistant_dock
            self.assertEqual(calls, [window])
            self.assertIsInstance(dock.widget(), NabiAssistantPanel)
            self.assertTrue(
                dock.features() & QDockWidget.DockWidgetFeature.DockWidgetClosable
            )
            dock.close()
            self.assertFalse(dock.isVisible())
        finally:
            window.close()

    def test_factory_invalida_falha_sem_instalar_area_parcial(self):
        class Application:
            new_session = staticmethod(PDVSession)

        with self.assertRaisesRegex(TypeError, "QWidget"):
            create_application(
                Application(), argv=[], assistant_panel_factory=lambda _parent: object()
            )


if __name__ == "__main__":
    unittest.main()
