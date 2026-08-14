import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
APP = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")


def method_source(name):
    node = next(node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(SOURCE, node) or ""


def test_root_is_created_with_dark_surface_before_withdraw():
    constructor = method_source("__init__")
    assert 'super().__init__(fg_color="#0d1117")' in constructor
    assert constructor.index('super().__init__(fg_color="#0d1117")') < constructor.index("self.withdraw()")


def test_closing_summary_uses_grouped_metric_cards_instead_of_dense_text():
    closing = method_source("_abrir_fechamento_sessao")
    assert "def metric_card" in closing
    assert 'text="DINHEIRO FÍSICO"' in closing
    assert 'text="ELETRÔNICOS"' in closing
    for title in ("SALDO INICIAL", "VENDAS", "RECEBIMENTOS", "SUPRIMENTOS", "SANGRIAS", "DINHEIRO ESPERADO", "PIX", "CARTÃO", "OUTROS"):
        assert f'"{title}"' in closing
    assert "detail =" not in closing
