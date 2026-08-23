from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from assistant_nabi import AssistantTurn, ToolResult, UnavailableAssistantService

try:
    from PySide6.QtWidgets import QApplication
    from ui_qt.assistant_nabi import NabiAssistantPanel
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
        self.assertEqual(self.panel.status.property("nabiState"), "warning")

    def test_mascote_oficial_tem_transparencia_real_e_descricao_acessivel(self):
        asset = (
            Path(__file__).resolve().parents[1]
            / "ui_qt"
            / "assistant_nabi"
            / "assets"
            / "nabi_mascot_blue_v2_transparent.png"
        )
        self.assertTrue(asset.is_file())
        pixmap = self.panel.mascot.pixmap()
        self.assertIsNotNone(pixmap)
        self.assertFalse(pixmap.isNull())
        image = pixmap.toImage()
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        self.assertIn("Disponível", self.panel.mascot.accessibleDescription())

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
        self.assertEqual(self.panel.status.property("nabiState"), "available")

    def test_falha_segura_aparece_como_bloqueada(self):
        self.panel._generation = 2
        self.panel._complete(2, AssistantTurn("Modelo indisponível", safe_failure=True))
        self.assertEqual(self.panel.status.text(), "Bloqueada")
        self.assertEqual(self.panel.status.property("nabiState"), "blocked")

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

    def test_servico_indisponivel_desativa_entrada_sem_impedir_painel(self):
        panel = NabiAssistantPanel(
            UnavailableAssistantService("Modelo e sessão ainda não homologados.")
        )
        self.addCleanup(panel.close)
        self.assertFalse(panel.message.isEnabled())
        self.assertFalse(panel.send.isEnabled())
        self.assertEqual(panel.status.text(), "Em preparação")
        self.assertEqual(panel.status.property("nabiState"), "offline")
        self.assertIn("ainda não homologados", panel.history.toPlainText())
        panel.reactivate()
        self.assertFalse(panel.send.isEnabled())


if __name__ == "__main__":
    unittest.main()
