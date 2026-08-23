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


class Activation:
    def __init__(self):
        self.active = False
        self.stops = 0

    def stop(self):
        self.active = False
        self.stops += 1


class DraftService(Service):
    def __init__(self):
        self.invalidations = 0
        self.reviews = []
        self.confirmations = []

    def invalidate_confirmations(self):
        self.invalidations += 1

    def review_draft(self, draft_id, fingerprint):
        self.reviews.append((draft_id, fingerprint))
        return type("Challenge", (), {"token": "token-seguro"})()

    def confirm_draft(self, token, draft_id, fingerprint):
        self.confirmations.append((token, draft_id, fingerprint))
        return object(), object()

    def confirm_and_execute_purchase(self, token, draft_id, fingerprint):
        self.confirmations.append((token, draft_id, fingerprint))
        result = type("Result", (), {
            "recebimento_id": 77, "status_pedido": "PARCIAL",
        })()
        return result, object()


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

    def test_ativacao_autenticada_libera_texto_e_oculta_botao(self):
        activation = Activation()
        panel = NabiAssistantPanel(
            UnavailableAssistantService("Autenticação necessária."),
            activation_manager=activation,
        )
        self.addCleanup(panel.close)
        self.assertFalse(panel.activate_button.isHidden())
        panel._generation = 7
        panel._busy = True
        activation.active = True
        panel._activation_complete(7, Service(), None)
        self.assertTrue(panel.send.isEnabled())
        self.assertFalse(panel.activate_button.isVisible())
        self.assertEqual(panel.status.property("nabiState"), "available")
        self.assertIn("rascunhos seguros", panel.history.toPlainText())

    def test_falha_de_ativacao_nao_expoe_credencial_nem_libera_texto(self):
        activation = Activation()
        panel = NabiAssistantPanel(
            UnavailableAssistantService("Autenticação necessária."),
            activation_manager=activation,
        )
        self.addCleanup(panel.close)
        panel._generation = 8
        panel._busy = True
        panel._activation_complete(8, None, PermissionError("Usuário ou senha inválidos."))
        self.assertFalse(panel.send.isEnabled())
        self.assertTrue(panel.activate_button.isEnabled())
        self.assertEqual(panel.status.property("nabiState"), "blocked")
        self.assertNotIn("segredo", panel.history.toPlainText())

    def test_parar_encerra_runtime_autenticado_e_exige_novo_login(self):
        activation = Activation()
        activation.active = True
        panel = NabiAssistantPanel(Service(), activation_manager=activation)
        self.addCleanup(panel.close)
        panel.stop_nabi()
        self.assertEqual(activation.stops, 1)
        self.assertFalse(panel.send.isEnabled())
        self.assertFalse(panel.activate_button.isHidden())
        panel.reactivate()
        self.assertFalse(panel.send.isEnabled())
        self.assertEqual(panel.status.text(), "Autenticação necessária")

    def test_rascunho_exige_revisao_e_confirmacao_humana_separadas(self):
        service = DraftService()
        transferred = []
        panel = NabiAssistantPanel(
            service, draft_transfer=lambda draft, authorization: transferred.append(
                (draft, authorization)
            )
        )
        self.addCleanup(panel.close)
        panel._generation = 5
        panel._complete(5, AssistantTurn("Rascunho", (ToolResult(
            "req", "vendas.criar_rascunho", True,
            {
                "draft_id": "draft-1", "fingerprint": "a" * 64,
                "items": [], "total": "10.00", "payment_method": "PIX",
            },
        ),)))
        self.assertFalse(panel.review_draft_button.isHidden())
        self.assertTrue(panel.confirm_draft_button.isHidden())
        panel.review_draft()
        self.assertEqual(service.reviews, [("draft-1", "a" * 64)])
        self.assertFalse(panel.confirm_draft_button.isHidden())
        panel.confirm_draft()
        self.assertEqual(service.confirmations[0][0], "token-seguro")
        self.assertEqual(len(transferred), 1)
        self.assertIn("Nenhuma venda foi registrada", panel.history.toPlainText())

    def test_rascunho_por_valor_e_estoque_tambem_habilita_revisao(self):
        service = DraftService()
        panel = NabiAssistantPanel(service, draft_transfer=lambda *_: None)
        self.addCleanup(panel.close)
        panel._generation = 6
        panel._complete(6, AssistantTurn("Sugestão", (ToolResult(
            "req-target", "vendas.sugerir_rascunho_por_estoque", True,
            {
                "draft_id": "draft-target", "fingerprint": "b" * 64,
                "items": [], "total": "500.00", "payment_method": "PIX",
            },
        ),)))
        self.assertFalse(panel.review_draft_button.isHidden())
        self.assertIn("RASCUNHO", panel.history.toPlainText())

    def test_recebimento_exige_revisao_e_executa_pelo_servico_confirmado(self):
        service = DraftService()
        panel = NabiAssistantPanel(service)
        self.addCleanup(panel.close)
        panel._generation = 9
        panel._complete(9, AssistantTurn("Entrada", (ToolResult(
            "req-purchase", "compras.preparar_recebimento", True,
            {
                "draft_id": "purchase-1", "fingerprint": "c" * 64,
                "operation_kind": "PURCHASE_RECEIPT", "order_id": 7,
                "supplier_name": "FORNECEDOR", "total": "34.00",
                "items": [{
                    "quantity": "4.0000", "description": "CAFÉ",
                    "unit_cost": "8.50", "line_total": "34.00",
                }],
            },
        ),)))
        self.assertFalse(panel.review_draft_button.isHidden())
        self.assertIn("nenhum recebimento", panel.history.toPlainText())
        panel.review_draft()
        panel.confirm_draft()
        self.assertEqual(service.confirmations[0][1], "purchase-1")
        self.assertIn("Registro #77", panel.history.toPlainText())
        self.assertEqual(panel.status.text(), "Recebimento registrado")


if __name__ == "__main__":
    unittest.main()
