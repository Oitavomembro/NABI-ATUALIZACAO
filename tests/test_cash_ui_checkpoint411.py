import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
APP = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")


def method_source(name):
    node = next(node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(SOURCE, node) or ""


def test_dashboard_has_no_legacy_cash_or_closing_buttons():
    dashboard = method_source("tela_dashboard")
    assert "Movimentação de Caixa" not in dashboard
    assert "Finalizar dia" not in dashboard
    assert "abrir_fechamento_caixa" not in dashboard


def test_cash_screen_keeps_navigation_and_explicit_return():
    screen = method_source("tela_caixa")
    assert 'self.mostrar_tela("dashboard")' in screen
    for destination in ("dashboard", "vendas", "clientes", "produtos", "configs"):
        assert f'self.botoes_topo["{destination}"]' in SOURCE


def test_open_and_closed_states_show_only_valid_actions():
    update = method_source("atualizar_tela_caixa")
    assert "self.frame_caixa_abertura.pack_forget()" in update
    assert "self.frame_caixa_acoes.pack_forget()" in update
    assert "if aberto:" in update


def test_cash_actions_use_nabicode_modals_without_native_dialogs():
    for name in ("_abrir_movimento_sessao", "_detalhar_caixa_historico"):
        source = method_source(name)
        assert "_criar_modal_nabicode" in source
        assert "_mostrar_modal_nabicode" in source
        assert "simpledialog" not in source
        assert "messagebox" not in source
        assert 'attributes("-alpha"' not in source
    closing = method_source("_abrir_fechamento_sessao")
    assert "simpledialog" not in closing
    assert "messagebox" not in closing
    assert "grab_set()" not in closing
    assert "CASH_CLOSE_READY" in closing


def test_cash_layout_contains_cards_actions_movements_and_history():
    screen = method_source("tela_caixa")
    for text in ("DINHEIRO NA GAVETA", "MOVIMENTO TOTAL", "PIX", "CARTÃO", "RECEBIMENTOS", "SANGRIAS", "SUPRIMENTOS", "MOVIMENTAÇÕES DA SESSÃO ATUAL", "HISTÓRICO DE SESSÕES"):
        assert text in screen


def test_cash_opening_modals_do_not_use_alpha_fade():
    for name in ("perguntar_abertura_caixa", "abrir_formulario_abertura_caixa"):
        source = method_source(name)
        assert "_criar_modal_nabicode" in source
        assert "_mostrar_modal_nabicode" in source
        assert "reveal_prepared_toplevel_smooth" not in source
        assert 'attributes("-alpha"' not in source
