import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
APP = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")


def method_source(name):
    node = next(node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(SOURCE, node) or ""


def test_root_repaint_runs_after_resize_and_restore():
    constructor = method_source("__init__")
    assert 'self.bind("<Configure>", self._agendar_redesenho_interface, add="+")' in constructor
    assert 'self.bind("<Map>", self._agendar_redesenho_interface, add="+")' in constructor


def test_repaint_covers_visible_widget_tree_and_current_background():
    source = method_source("_redesenhar_interface")
    assert "manager.refresh(tela, immediate=True)" in source
    assert "pending = [self]" in source
    assert "widget.winfo_viewable()" in source
    assert 'widget.event_generate("<Expose>")' in source
    assert "pending.extend(widget.winfo_children())" in source
    assert "except Exception" not in source
