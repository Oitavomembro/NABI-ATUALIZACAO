import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
APP = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")


def method_source(name):
    node = next(node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(SOURCE, node) or ""


def test_all_cash_windows_use_one_factory_and_no_modal_blocking():
    names = ("_abrir_movimento_sessao", "_abrir_fechamento_sessao", "_detalhar_caixa_historico", "perguntar_abertura_caixa", "abrir_formulario_abertura_caixa")
    for name in names:
        source = method_source(name)
        assert "_criar_modal_nabicode" in source
        assert "grab_set" not in source
        assert "wait_window" not in source
        assert "wait_variable" not in source
        assert "transient(" not in source
        assert "focus_force" not in source
        assert "prepare_hidden_toplevel" not in source
        assert "reveal_prepared_toplevel" not in source


def test_shared_factory_has_no_grab_transient_topmost_or_visibility_toggle():
    source = method_source("_criar_modal_nabicode") + method_source("_mostrar_modal_nabicode")
    for forbidden in ("grab_set", "transient(", "-topmost", "withdraw(", "deiconify(", "focus_force", "after(", "after_idle("):
        assert forbidden not in source


def test_minimal_modal_uses_same_factory_without_business_dependencies():
    source = method_source("_abrir_teste_modal_caixa")
    assert '"TESTE MODAL"' in source
    assert "_criar_modal_nabicode" in source
    assert "_servico_caixa" not in source
    assert "grab_set" not in source


def test_session_creation_has_exactly_two_explicit_sources():
    source = method_source("_solicitar_criacao_sessao_caixa")
    assert '"OPEN_WITH_VALUE"' in source
    assert '"OPEN_WITHOUT_VALUE"' in source
    assert "CASH_SESSION_CREATE_REQUEST" in source
    assert "CASH_SESSION_CREATE_REJECTED" in source
    direct_calls = [node for node in ast.walk(APP) if isinstance(node, ast.Attribute) and node.attr == "open_session"]
    assert len(direct_calls) == 1


def test_opening_cancel_escape_and_x_do_not_create_session():
    form = method_source("abrir_formulario_abertura_caixa")
    close_block = form.split("def fechar_formulario", 1)[1].split("def salvar", 1)[0]
    assert "_solicitar_criacao_sessao_caixa" not in close_block
    assert 'bind("<Escape>"' in form
    assert 'protocol("WM_DELETE_WINDOW", fechar_formulario)' in form
    assert "if not valor.get().strip()" in form
