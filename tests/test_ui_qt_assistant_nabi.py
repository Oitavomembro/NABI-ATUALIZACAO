from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from assistant_nabi import AssistantTurn, ToolResult, UnavailableAssistantService
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

    def confirm_and_execute_nfe_entry(self, token, draft_id, fingerprint):
        self.confirmations.append((token, draft_id, fingerprint))
        return {"importacao_id": 88, "itens_vinculados": 2}, object()

    def confirm_and_execute_customer(self, token, draft_id, fingerprint):
        self.confirmations.append((token, draft_id, fingerprint))
        return SimpleNamespace(customer_id=45, record_number=5501), object()

    def confirm_and_execute_customer_receipt(self, token, draft_id, fingerprint):
        self.confirmations.append((token, draft_id, fingerprint))
        return SimpleNamespace(resource_id=92), object()


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

    def test_renderiza_resumo_financeiro_sem_documentos(self):
        result = ToolResult("r-fin", "financeiro.resumo", True, {
            "start_date": "2026-08-01", "end_date": "2026-08-23",
            "receivable_open": "100.00", "receivable_overdue": "20.00",
            "payable_open": "70.00", "payable_due_today": "10.00",
            "received_in_period": "50.00", "paid_in_period": "30.00",
        })
        text = self.panel._result_text(result)
        self.assertIn("A receber aberto: R$ 100.00", text)
        self.assertIn("Pago: R$ 30.00", text)
        self.assertNotIn("documento", text.casefold())

    def test_renderiza_listas_financeiras_sem_campos_ocultos(self):
        result = ToolResult("r-titles", "financeiro.listar_receber", True, {
            "items": [{
                "title_id": 41, "customer_id": 9, "customer_name": "MARIA",
                "open_amount": "80.00", "due_date": "2026-08-30",
                "status": "PARCIAL", "overdue": False,
            }]
        })
        text = self.panel._result_text(result)
        self.assertIn("Título #41 — Cliente #9 MARIA", text)
        self.assertIn("R$ 80.00", text)
        for hidden in ("documento", "origem", "observação", "centro de custo"):
            self.assertNotIn(hidden, text.casefold())

    def test_renderiza_indicadores_e_caixa_deterministicamente(self):
        indicators = ToolResult("r-ind", "relatorios.consultar_indicadores", True, {
            "start_date": "2026-08-01", "end_date": "2026-08-24",
            "sales_total": "120.50", "receivable_open": "80.00",
            "payable_open": "30.25", "low_stock": 4, "active_customers": 17,
        })
        cash = ToolResult("r-cash", "caixa.consultar_atual", True, {
            "is_open": True, "session_id": 7, "opened_at": "2026-08-24 08:00:00",
            "opening_balance": "100.00", "expected_cash": "180.00",
            "cash_sales": "50.00", "pix_sales": "20.00", "card_sales": "10.00",
            "other_sales": "0.00", "cash_receipts": "15.00",
            "supplies": "5.00", "withdrawals": "20.00",
        })
        indicator_text = self.panel._result_text(indicators)
        cash_text = self.panel._result_text(cash)
        self.assertIn("Clientes ativos: 17", indicator_text)
        self.assertIn("Dinheiro esperado: R$ 180.00", cash_text)
        self.assertNotIn("observação", cash_text.casefold())

    def test_renderiza_estoque_baixo_deterministicamente(self):
        result = ToolResult("r-stock", "estoque.listar_baixo", True, {
            "items": [{
                "product_id": 7, "code": "P7", "description": "CAFÉ",
                "current_quantity": "1.0000", "minimum_quantity": "3.0000",
            }]
        })
        self.assertEqual(
            self.panel._result_text(result),
            "P7 — CAFÉ — atual 1.0000 — mínimo 3.0000",
        )

    def test_renderiza_compras_sem_campos_ocultos(self):
        suppliers = ToolResult("r-s", "compras.listar_fornecedores", True, {
            "items": [{"supplier_id": 2, "name": "NABI", "active": True}],
        })
        orders = ToolResult("r-o", "compras.listar_pedidos", True, {
            "items": [{"order_id": 7, "supplier_name": "NABI", "status": "ABERTO",
                       "total": "20.50", "pending_quantity": "2.0000"}],
        })
        detail = ToolResult("r-d", "compras.consultar_pedido", True, {
            "order_id": 7, "supplier_name": "NABI", "status": "PARCIAL",
            "items": [{"code": "P5", "description": "CAFÉ",
                       "ordered_quantity": "3.0000", "received_quantity": "1.0000",
                       "pending_quantity": "2.0000", "unit_cost": "8.25"}],
        })
        self.assertEqual(
            self.panel._result_text(suppliers), "Fornecedor #2 — NABI — ativo"
        )
        self.assertIn("Pedido #7 — NABI — ABERTO", self.panel._result_text(orders))
        self.assertIn("P5 — CAFÉ", self.panel._result_text(detail))

    def test_renderiza_rascunhos_de_fornecedor_pedido_produto_e_estoque(self):
        supplier = ToolResult("s", "compras.preparar_fornecedor", True, {
            "name": "NABI", "legal_name": "NABI LTDA", "document": "123",
            "phone": "71", "email": "a@b.com",
        })
        order = ToolResult("o", "compras.preparar_pedido", True, {
            "supplier_name": "NABI", "total": "20.00",
            "items": [{"quantity": "2", "code": "P1", "description": "CAFÉ",
                       "unit_cost": "10.00", "line_total": "20.00"}],
        })
        product = ToolResult("p", "produtos.preparar_cadastro", True, {
            "code": "P1", "description": "CAFÉ", "sale_price": "15.00",
            "cost_price": "10.00", "current_stock": "0.0000",
            "minimum_stock": "2.0000",
        })
        stock = ToolResult("e", "estoque.preparar_movimento", True, {
            "product_id": 1, "product_code": "P1", "product_description": "CAFÉ",
            "previous_balance": "5.0000", "new_balance": "7.0000", "reason": "COMPRA",
        })
        self.assertIn("nenhum fornecedor", self.panel._result_text(supplier))
        self.assertIn("Total proposto: R$ 20.00", self.panel._result_text(order))
        self.assertIn("estoque inicial: 0.0000", self.panel._result_text(product).casefold())
        self.assertIn("novo saldo: 7.0000", self.panel._result_text(stock))

    def test_renderiza_rascunhos_financeiros_sem_declarar_persistencia(self):
        title = ToolResult("t", "financeiro.preparar_titulo", True, {
            "title_type": "PAGAR", "amount": "150.00", "party_id": 3,
            "party_name": "FORNECEDOR", "due_date": "2026-09-10", "document": "NF1",
        })
        settlement = ToolResult("b", "financeiro.preparar_baixa", True, {
            "title_type": "RECEBER", "title_id": 9, "previous_open_amount": "100.00",
            "amount": "40.00", "expected_open_amount": "60.00",
            "payment_method": "PIX", "payment_date": "2026-08-24",
        })
        self.assertIn("nenhum título foi criado", self.panel._result_text(title))
        preview = self.panel._result_text(settlement)
        self.assertIn("saldo esperado R$ 60.00", preview)
        self.assertIn("nenhuma baixa foi registrada", preview)

    def test_intencao_abre_pesquisa_por_porta_explicita_uma_vez(self):
        opened = []
        panel = NabiAssistantPanel(
            Service(), product_search_opener=lambda term: opened.append(term) or True
        )
        self.addCleanup(panel.close)
        turn = AssistantTurn("Vou abrir a pesquisa.", (ToolResult(
            "r-ui", "interface.abrir_pesquisa_produtos", True,
            {"action": "OPEN_PRODUCT_SEARCH", "term": "café"},
        ),))
        panel._generation = 4
        panel._complete(4, turn)
        self.assertEqual(opened, ["café"])
        self.assertIn("Pesquisa ampliada solicitada para: café", panel.history.toPlainText())

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

    def test_revisao_xml_exibe_evidencia_sem_declarar_importacao(self):
        panel = NabiAssistantPanel(Service(), nfe_entry_service=object())
        self.addCleanup(panel.close)
        draft = SimpleNamespace(
            number="123", supplier_name="FORNECEDOR", access_key="35" * 22,
            protocol_status_evidence="100",
            items=(SimpleNamespace(
                index=0, quantity="2.0000", unit="UN", description="CAFÉ",
                match_status="VINCULAR", match_criterion="EAN",
            ),),
        )
        panel._generation = 12
        panel._busy = True
        panel._nfe_entry_complete(12, draft, None)
        text = panel.history.toPlainText()
        self.assertIn("Evidência cStat", text)
        self.assertIn("SOMENTE REVISÃO", text)
        self.assertIn("nenhum produto, estoque ou financeiro", text)
        self.assertEqual(panel.status.text(), "XML aguardando revisão manual")

    def test_entrada_nfe_exata_exige_duas_etapas_e_informa_ausencia_de_sefaz(self):
        service = DraftService()
        panel = NabiAssistantPanel(service)
        self.addCleanup(panel.close)
        panel._generation = 13
        panel._complete(13, AssistantTurn("Entrada preparada", (ToolResult(
            "req-nfe", "compras.preparar_entrada_nfe_exata", True,
            {
                "draft_id": "nfe-1", "fingerprint": "d" * 64,
                "operation_kind": "NFE_ENTRY_IMPORT", "number": "123",
                "supplier_name": "FORNECEDOR", "document_total": "42.00",
                "items": [{
                    "product_id": 7, "description": "CAFÉ",
                    "xml_quantity": "2.0000", "conversion_factor": "1.0000",
                    "stock_quantity": "2.0000", "unit_cost": "21.00",
                }],
            },
        ),)))
        self.assertFalse(panel.review_draft_button.isHidden())
        panel.review_draft()
        panel.confirm_draft()
        self.assertEqual(service.confirmations[0][1], "nfe-1")
        self.assertIn("Importação #88", panel.history.toPlainText())
        self.assertIn("Nenhuma comunicação com a SEFAZ", panel.history.toPlainText())
        self.assertEqual(panel.status.text(), "Entrada de NF-e registrada")

    def test_cadastro_cliente_exige_revisao_e_servico_confirmado(self):
        service = DraftService()
        panel = NabiAssistantPanel(service)
        self.addCleanup(panel.close)
        panel._generation = 14
        panel._complete(14, AssistantTurn("Cadastro preparado", (ToolResult(
            "req-customer", "clientes.preparar_cadastro", True,
            {
                "draft_id": "customer-1", "fingerprint": "e" * 64,
                "operation_kind": "CUSTOMER_CREATE", "record_number": 5501,
                "name": "MARIA", "credit_limit": "500.00",
            },
        ),)))
        self.assertFalse(panel.review_draft_button.isHidden())
        panel.review_draft()
        self.assertIn("ficha, nome", panel.history.toPlainText())
        panel.confirm_draft()
        self.assertEqual(service.confirmations[0][1], "customer-1")
        self.assertIn("Ficha 5501", panel.history.toPlainText())
        self.assertEqual(panel.status.text(), "Cliente cadastrado")

    def test_recebimento_cliente_exibe_saldos_e_exige_confirmacao(self):
        service = DraftService(); panel = NabiAssistantPanel(service)
        self.addCleanup(panel.close)
        panel._generation = 15
        panel._complete(15, AssistantTurn("Recebimento preparado", (ToolResult(
            "req-receipt", "clientes.preparar_recebimento", True,
            {
                "draft_id": "receipt-1", "fingerprint": "f" * 64,
                "operation_kind": "CUSTOMER_RECEIPT", "record_number": 3321,
                "customer_name": "GUSTAVO", "amount": "100.00",
                "previous_balance": "203.00", "expected_balance": "103.00",
                "payment_method": "PIX", "payment_date": "2026-08-24",
            },
        ),)))
        self.assertFalse(panel.review_draft_button.isHidden())
        preview = panel.history.toPlainText()
        self.assertIn("Saldo antes: R$ 203.00", preview)
        self.assertIn("Saldo restante: R$ 103.00", preview)
        self.assertIn("nenhum pagamento foi registrado", preview)
        panel.review_draft(); panel.confirm_draft()
        self.assertEqual(service.confirmations[0][1], "receipt-1")
        self.assertIn("Movimento #92", panel.history.toPlainText())
        self.assertEqual(panel.status.text(), "Recebimento registrado")

    def test_resposta_xml_atrasada_e_ignorada_apos_parar(self):
        panel = NabiAssistantPanel(Service(), nfe_entry_service=object())
        self.addCleanup(panel.close)
        panel._generation = 20
        panel.stop_nabi()
        before = panel.history.toPlainText()
        panel._nfe_entry_complete(20, None, ValueError("não mostrar"))
        self.assertEqual(panel.history.toPlainText(), before)


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

    def test_servico_e_factory_nao_podem_disputar_o_mesmo_dock(self):
        class Application:
            new_session = staticmethod(PDVSession)

        with self.assertRaisesRegex(ValueError, "não ambos"):
            create_application(
                Application(), argv=[], assistant_service=Service(),
                assistant_panel_factory=lambda parent: NabiAssistantPanel(Service(), parent),
            )


if __name__ == "__main__":
    unittest.main()
