from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from assistant_nabi import AssistantActor, AssistantTurn, DraftToolRegistry, ToolRequest, ToolResult
from assistant_nabi.ui_tools import register_ui_intent_tools
from PySide6.QtWidgets import QApplication
from ui_qt.assistant_nabi import NabiAssistantPanel


class _Permissions:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def allows(self, actor, module, action):
        return self.allowed


class _Audit:
    def __init__(self):
        self.events = []

    def record(self, **event):
        self.events.append(event)


class _Service:
    def ask(self, message):
        return AssistantTurn(message)


def _application():
    return QApplication.instance() or QApplication([])


def _registry(*, allowed=True):
    audit = _Audit()
    registry = DraftToolRegistry(
        permissions=_Permissions(allowed), audit=audit
    )
    register_ui_intent_tools(registry)
    return registry, audit, AssistantActor("operador", "ADMIN", "sessao")


def test_explica_configuracao_sem_dados_operacionais_ou_segredos():
    registry, audit, actor = _registry()

    result = registry.execute(ToolRequest(
        "contexto.explicar_configuracao", {"area": "FISCAL"}
    ), actor=actor)

    assert result.success
    assert result.payload["area"] == "FISCAL"
    text = " ".join(str(value) for value in result.payload.values()).casefold()
    assert "não recebe senha" in text
    assert "não transmite" in text
    assert len(audit.events) == 1


def test_area_livre_e_parametro_extra_falham_fechado():
    registry, _audit, actor = _registry()

    invented = registry.execute(ToolRequest(
        "contexto.explicar_configuracao", {"area": "LIBERAR_SEFAZ"}
    ), actor=actor)
    secret = registry.execute(ToolRequest(
        "interface.abrir_configuracao_fiscal", {"senha": "segredo"}
    ), actor=actor)

    assert not invented.success
    assert not secret.success


def test_intencoes_sao_fechadas_sem_arquivo_id_ou_confirmacao():
    registry, _audit, actor = _registry()
    expected = {
        "interface.abrir_configuracao_fiscal": "OPEN_FISCAL_CONFIGURATION",
        "interface.abrir_importacao_xml_empresa": "OPEN_COMPANY_XML_IMPORT",
        "interface.abrir_importacao_xml_produtos": "OPEN_PRODUCT_XML_IMPORT",
    }

    for tool_name, action in expected.items():
        result = registry.execute(ToolRequest(tool_name, {}), actor=actor)
        injected = registry.execute(ToolRequest(
            tool_name, {"path": "C:/segredo.xml", "confirm": True}
        ), actor=actor)
        assert result.success
        assert result.payload == {"action": action}
        assert not injected.success


def test_permissao_recusada_impede_intencao_e_audita():
    registry, audit, actor = _registry(allowed=False)

    result = registry.execute(ToolRequest(
        "interface.abrir_importacao_xml_produtos", {}
    ), actor=actor)

    assert not result.success
    assert result.message == "Permissão insuficiente."
    assert len(audit.events) == 1


def test_painel_encaminha_cada_porta_explicita_exatamente_uma_vez():
    app = _application()
    opened = []
    panel = NabiAssistantPanel(
        _Service(),
        fiscal_configuration_opener=lambda: opened.append("fiscal"),
        company_xml_import_opener=lambda: opened.append("empresa"),
        product_xml_import_opener=lambda: opened.append("produtos"),
    )
    try:
        results = tuple(
            ToolResult(str(index), name, True, {"action": action})
            for index, (name, action) in enumerate((
                ("interface.abrir_configuracao_fiscal", "OPEN_FISCAL_CONFIGURATION"),
                ("interface.abrir_importacao_xml_empresa", "OPEN_COMPANY_XML_IMPORT"),
                ("interface.abrir_importacao_xml_produtos", "OPEN_PRODUCT_XML_IMPORT"),
            ))
        )
        panel._generation = 1
        panel._complete(1, AssistantTurn("Abrindo telas oficiais.", results))
        assert opened == ["fiscal", "empresa", "produtos"]
    finally:
        panel.close()


def test_painel_sem_porta_nao_improvisa_clique_ou_abertura():
    app = _application()
    panel = NabiAssistantPanel(_Service())
    try:
        panel._generation = 2
        panel._complete(2, AssistantTurn("Tentativa.", (ToolResult(
            "1", "interface.abrir_configuracao_fiscal", True,
            {"action": "OPEN_FISCAL_CONFIGURATION"},
        ),)))
        assert "não está disponível nesta tela" in panel.history.toPlainText()
    finally:
        panel.close()


def test_falha_da_porta_fecha_sem_escapar_para_a_interface():
    app = _application()
    panel = NabiAssistantPanel(
        _Service(), fiscal_configuration_opener=lambda: (_ for _ in ()).throw(
            PermissionError("recusada")
        ),
    )
    try:
        panel._generation = 3
        panel._complete(3, AssistantTurn("Tentativa.", (ToolResult(
            "1", "interface.abrir_configuracao_fiscal", True,
            {"action": "OPEN_FISCAL_CONFIGURATION"},
        ),)))
        assert panel.status.property("nabiState") == "blocked"
        assert "não pôde ser aberta com segurança" in panel.history.toPlainText()
        assert "recusada" not in panel.history.toPlainText()
    finally:
        panel.close()


def test_inicio_automatico_usa_sessao_existente_sem_expor_senha():
    app = _application()

    class Activation:
        def __init__(self): self.calls = 0
        def activate_current_session(self):
            self.calls += 1
            return _Service()

    class InlinePool:
        @staticmethod
        def start(worker): worker.run()

    activation = Activation()
    panel = NabiAssistantPanel(
        _Service(), activation_manager=activation, thread_pool=InlinePool(),
        auto_activate=True,
    )
    try:
        assert activation.calls == 1
        assert panel.activate_button.isHidden()
        assert panel.send.isEnabled()
        assert "Sessão autenticada" in panel.history.toPlainText()
    finally:
        panel.close()
