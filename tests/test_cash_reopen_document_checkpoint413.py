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


def test_opening_and_closing_dialogs_have_single_instance_guards():
    opening = method_source("abrir_formulario_abertura_caixa")
    closing = method_source("_abrir_fechamento_sessao")
    assert '_criar_modal_nabicode("ABERTURA_VALOR"' in opening
    assert '_criar_modal_nabicode("FECHAMENTO"' in closing


def test_closing_receipt_uses_official_80mm_pipeline_off_ui_thread():
    source = method_source("_imprimir_comprovante_fechamento_caixa")
    assert ".print_text(" in source
    assert 'output_format="Cupom 80 mm"' in source
    assert "threading.Thread" in source
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


def test_closing_print_dispatch_has_duplicate_guard_and_single_job_contract():
    source = method_source("_imprimir_comprovante_fechamento_caixa")
    assert "_cash_print_dispatch_lock" in source
    assert "_cash_printed_closings" in source
    assert "CASH_CLOSE_PRINT_DUPLICATE_BLOCKED" in source
    closing = method_source("_abrir_fechamento_sessao")
    assert 'closing["submitting"]' in closing
    assert 'confirm_button.configure(state="disabled"' in closing


def test_two_dispatch_attempts_for_same_closing_create_only_one_mock_job():
    calls = []

    class ImmediateThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

    class Printer:
        def print_text(self, text, **kwargs):
            calls.append((text, kwargs))
            return "IMPRESSORA MOCK"

    class App:
        _texto_comprovante_fechamento_caixa = staticmethod(lambda _session, _resumo: "NABICODE\nFECHAMENTO DE CAIXA\n")
        _servico_impressao = lambda self: Printer()
        after = lambda self, _delay, callback: callback()
        mostrar_notificacao = lambda self, *_args, **_kwargs: None

    namespace = {
        "threading": SimpleNamespace(Lock=threading.Lock, Thread=ImmediateThread),
        "obter_config": lambda _key: "Padrão do Sistema",
        "logger": SimpleNamespace(exception=lambda *_a, **_k: None, warning=lambda *_a, **_k: None),
    }
    exec(textwrap.dedent(method_source("_imprimir_comprovante_fechamento_caixa")), namespace)
    app = App()
    session = SimpleNamespace(id=19)
    assert namespace["_imprimir_comprovante_fechamento_caixa"](app, session, {}) is True
    assert namespace["_imprimir_comprovante_fechamento_caixa"](app, session, {}) is False
    assert len(calls) == 1
    assert calls[0][0].count("NABICODE") == 1
    assert calls[0][0].count("FECHAMENTO DE CAIXA") == 1


def test_startup_window_order_is_instrumented_without_alpha_zero():
    for event in ("APP_START", "ROOT_CREATED", "ROOT_WITHDRAWN", "SPLASH_CREATED", "SPLASH_VISIBLE", "ROOT_LAYOUT_READY", "SPLASH_DESTROY_START", "SPLASH_DESTROY_END", "ROOT_DEICONIFY", "ROOT_VISIBLE"):
        assert event in MAIN
    assert 'app.attributes("-alpha", 0.0)' not in MAIN


def test_cash_startup_dialog_order_is_instrumented():
    for event in ("CASH_STARTUP_CHECK", "CASH_DIALOG_CREATE", "CASH_DIALOG_VISIBLE"):
        assert event in LEGACY
