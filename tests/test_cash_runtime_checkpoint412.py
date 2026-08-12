import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
TREE = ast.parse(LEGACY)
APP = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")


def method_source(name):
    node = next(node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(LEGACY, node) or ""


def test_startup_handoff_has_no_alpha_animation_or_recursive_fade():
    assert "fade_main_in" not in MAIN
    assert 'app.attributes("-alpha", 0.0)' not in MAIN
    assert 'app.attributes("-alpha", 1.0)' in MAIN


def test_required_runtime_events_are_logged():
    combined = MAIN + LEGACY
    for event in ("START_APP", "SPLASH_START", "SPLASH_END", "MAIN_READY", "CASH_CHECK", "CASH_MODAL_OPEN", "CASH_MODAL_CLOSE", "CASH_SCREEN_OPEN", "CASH_CLOSE_CLICK", "CASH_CLOSE_MODAL_OPEN", "CASH_CLOSE_MODAL_CLOSE"):
        assert event in combined


def test_startup_cash_modals_never_grab_main_window():
    for name in ("perguntar_abertura_caixa", "abrir_formulario_abertura_caixa"):
        source = method_source(name)
        assert "grab=True" not in source
        assert "wait_window" not in source
        assert "wait_variable" not in source
        assert "grab_set" not in source


def test_operational_cash_modals_have_explicit_safe_close():
    helper = method_source("_fechar_modal_caixa")
    assert "grab_current() == win" in helper
    assert "grab_release()" in helper
    for name in ("_abrir_movimento_sessao", "_detalhar_caixa_historico"):
        source = method_source(name)
        assert "_fechar_modal_caixa" in source
        assert 'protocol("WM_DELETE_WINDOW"' in source


def test_closing_modal_is_non_blocking_and_has_single_exit_path():
    source = method_source("_abrir_fechamento_sessao")
    assert "grab_set()" not in source
    assert "wait_window" not in source
    assert "wait_variable" not in source
    assert 'protocol("WM_DELETE_WINDOW", close)' in source
    assert 'bind("<Escape>", close)' in source
    assert source.count("_fechar_modal_caixa(win") == 1
    assert 'closing = {"done": False, "submitting": False}' in source


def test_cash_database_timeout_is_bounded_for_ui_callbacks():
    adapter = (ROOT / "controllers" / "legacy_backend_adapter.py").read_text(encoding="utf-8")
    assert "self.backend_context.connect(timeout=3)" in adapter


def test_modal_close_helper_releases_before_destroying():
    helper = method_source("_fechar_modal_caixa")
    assert helper.index("grab_release()") < helper.index("win.destroy()")
