import ast
import threading
import textwrap
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
TREE = ast.parse(LEGACY)
APP = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")


def method_source(name):
    node = next(node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(LEGACY, node) or ""


def test_startup_cash_check_is_single_and_cancelable():
    schedule = method_source("_agendar_pergunta_abertura_caixa")
    assert "_cash_startup_check_done" in schedule
    assert "if self._cash_startup_check_done" in schedule
    assert "_cash_startup_after_id" in schedule


def test_opening_form_close_never_schedules_another_opening_dialog():
    form = method_source("abrir_formulario_abertura_caixa")
    assert "after_idle(self.perguntar_abertura_caixa)" not in form
    assert "after(self.perguntar_abertura_caixa)" not in form
    assert "_solicitar_criacao_sessao_caixa" in form


def test_closing_startup_question_keeps_main_application_running():
    question = method_source("perguntar_abertura_caixa")
    close_block = question.split("def fechar_pergunta", 1)[1].split("def informar_agora", 1)[0]
    assert "_fechar_modal_caixa(win)" in close_block
    assert "_garantir_janela_principal_visivel()" in close_block
    assert "self.destroy()" not in close_block
    assert 'win.protocol("WM_DELETE_WINDOW", fechar_pergunta)' in question


def test_opening_and_closing_dialogs_have_single_instance_guards():
    opening = method_source("abrir_formulario_abertura_caixa")
    closing = method_source("_abrir_fechamento_sessao")
    assert '_criar_modal_nabicode("ABERTURA_VALOR"' in opening
    assert '_criar_modal_nabicode("FECHAMENTO"' in closing


def test_closing_receipt_uses_standard_preview_before_any_physical_print():
    source = method_source("_abrir_preview_fechamento_caixa")
    assert "janela_preview_documento(" in source
    assert 'categoria="fechamento"' in source
    assert ".print_text(" not in source
    assert "threading.Thread" not in source
    text = method_source("_texto_comprovante_fechamento_caixa")
    for field in ("FECHAMENTO DE CAIXA", "Saldo inicial", "Vendas dinheiro", "Recebimentos dinheiro", "Suprimentos", "Sangrias", "Dinheiro esperado", "PIX", "Cartão", "Valor contado", "Diferença"):
        assert field in text


def test_closing_receipt_has_only_nabicode_identity_and_no_livraria_contamination():
    source = method_source("_texto_comprovante_fechamento_caixa")
    namespace = {}
    exec(textwrap.dedent(source), namespace)
    session = SimpleNamespace(
        id=7,
        terminal="PDV-01",
        opened_by="OPERADOR",
        opened_at="2026-08-12 10:00:00",
        closed_by="OPERADOR",
        closed_at="2026-08-12 18:00:00",
        opening_balance=100,
        expected_cash=170,
        counted_cash=170,
        difference=0,
        closing_note="",
    )
    resumo = {
        "dinheiro": 0,
        "recebimentos_dinheiro": 0,
        "suprimentos": 100,
        "sangrias": 30,
        "pix": 0,
        "cartao": 0,
        "outros": 0,
        "recebimentos_eletronicos": 0,
    }
    fechamento = namespace["_texto_comprovante_fechamento_caixa"](session, resumo)
    assert "LIVRARIA NABI" not in fechamento.upper()
    assert "LIVRARIA" not in fechamento.upper()
    assert fechamento.count("NABICODE") == 1
    assert fechamento.count("FECHAMENTO DE CAIXA") == 1
    assert fechamento.count("Sessão: 7") == 1
    assert "MOVIMENTAÇÕES" not in fechamento
    assert "historico" not in fechamento.casefold()


def test_runtime_document_sources_have_no_livraria_nabi_variation():
    audited = (
        ROOT / "nabicode_legacy.py",
        ROOT / "services" / "printing_service.py",
        ROOT / "services" / "receipt_service.py",
        ROOT / "services" / "pdf_document_service.py",
        ROOT / "controllers" / "legacy_backend_adapter.py",
    )
    for path in audited:
        assert "livraria nabi" not in path.read_text(encoding="utf-8").casefold(), path


def test_closing_confirmation_has_single_submit_and_preview_is_separate():
    source = method_source("_abrir_preview_fechamento_caixa")
    assert "janela_preview_documento(" in source
    assert "print_text(" not in source
    closing = method_source("_abrir_fechamento_sessao")
    assert 'closing["submitting"]' in closing
    assert 'confirm_button.configure(state="disabled"' in closing


def test_opening_closing_preview_does_not_dispatch_mock_printer():
    previews = []
    class App:
        _texto_comprovante_fechamento_caixa = staticmethod(lambda _session, _resumo: "NABICODE\nFECHAMENTO DE CAIXA\n")
        janela_preview_documento = lambda self, text, **kwargs: previews.append((text, kwargs)) or "PREVIEW"

    namespace = {}
    exec(textwrap.dedent(method_source("_abrir_preview_fechamento_caixa")), namespace)
    app, session = App(), SimpleNamespace(id=19)
    assert namespace["_abrir_preview_fechamento_caixa"](app, session, {}) == "PREVIEW"
    assert len(previews) == 1
    assert previews[0][1]["categoria"] == "fechamento"
    assert previews[0][0].count("FECHAMENTO DE CAIXA") == 1


def test_closing_is_persisted_without_automatic_print_and_offers_explicit_actions():
    closing = method_source("_abrir_fechamento_sessao")
    actions = method_source("_abrir_acoes_fechamento_caixa")
    assert "_abrir_preview_fechamento_caixa" not in closing
    assert "_abrir_acoes_fechamento_caixa(closed_session, resumo)" in closing
    assert 'text="Visualizar / Imprimir"' in actions
    assert 'text="Voltar"' in actions
    assert "_abrir_preview_fechamento_caixa(session, resumo)" in actions


def test_standard_preview_uses_closing_printer_configuration_without_dispatch():
    preview = method_source("janela_preview_documento")
    assert '"impressora_historico" if categoria == "fechamento"' in preview
    assert "print_text(" not in method_source("_abrir_preview_fechamento_caixa")


def test_close_modal_has_required_timing_markers_and_no_print_on_creation():
    source = method_source("_abrir_fechamento_sessao")
    for marker in ("CASH_CLOSE_CLICK", "CASH_CLOSE_DATA_START", "CASH_CLOSE_DATA_END", "CASH_CLOSE_MODAL_CREATE", "CASH_CLOSE_MODAL_VISIBLE"):
        assert marker in source
    before_confirm = source.split("def confirm():", 1)[0]
    assert "_imprimir_comprovante_fechamento_caixa" not in before_confirm


def test_closing_modal_is_revealed_before_database_summary_is_loaded():
    source = method_source("_abrir_fechamento_sessao")
    assert source.index("self._mostrar_modal_nabicode(win)") < source.index("def carregar_fechamento")
    assert "self.after(1, carregar_fechamento)" in source


def test_startup_window_order_is_instrumented_without_alpha_zero():
    for event in ("APP_START", "ROOT_CREATED", "ROOT_WITHDRAWN", "SPLASH_CREATED", "SPLASH_VISIBLE", "ROOT_LAYOUT_READY", "SPLASH_DESTROY_START", "SPLASH_DESTROY_END", "ROOT_DEICONIFY", "ROOT_VISIBLE"):
        assert event in MAIN
    assert 'app.attributes("-alpha", 0.0)' not in MAIN


def test_cash_startup_dialog_order_is_instrumented():
    for event in ("CASH_STARTUP_CHECK", "CASH_DIALOG_CREATE", "CASH_DIALOG_VISIBLE"):
        assert event in LEGACY
