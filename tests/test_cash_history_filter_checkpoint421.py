import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
APP = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")


def method_source(name):
    node = next(node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(SOURCE, node) or ""


def test_cash_screen_keeps_history_and_movements_behind_compact_actions():
    screen = method_source("tela_caixa")
    assert 'text="Histórico por dia"' in screen
    assert 'text="Ver movimentações atuais"' in screen
    assert "ttk.Treeview" not in screen


def test_day_history_is_loaded_only_when_requested():
    history = method_source("_abrir_historico_caixa_por_dia")
    assert 'placeholder_text="DD/MM/AAAA"' in history
    assert "opened_date=date_entry.get()" in history
    assert 'date_entry.bind("<Return>", load)' in history


def test_card_details_reuse_current_summary_without_database_query():
    details = method_source("_abrir_detalhe_cartao_caixa")
    assert 'getattr(self, "_cash_current_summary", None)' in details
    assert "_servico_caixa" not in details
    for category in ("movement_total", "pix", "cartao", "recebimentos", "sangrias", "suprimentos"):
        assert f'"{category}"' in details
