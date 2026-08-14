import ast
from pathlib import Path

from services.ui_preferences import UIPreferencesService


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "nabicode_legacy.py"


def test_cash_is_an_official_navigation_module():
    assert UIPreferencesService.MODULE_LABELS["caixa"] == "Caixa"
    assert "caixa" in UIPreferencesService.MODULE_ORDER


def test_main_navigation_registers_button_and_screen():
    source = LEGACY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {
        node.name
        for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "FicharioMoveisApp"
        for node in item.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "tela_caixa" in methods
    assert 'self.botoes_topo["caixa"] = btn_caixa' in source
    assert '"caixa": self.tela_caixa' in source
    assert "UIPreferencesService.navigation_positions(" in source


def test_every_profile_keeps_cash_visible_even_with_legacy_preferences():
    legacy = {
        "mode": "Intermediário",
        "workspace": "Geral",
        "custom_navigation": True,
        "navigation_modules": ["dashboard", "vendas", "clientes", "produtos", "configs"],
    }
    assert "caixa" in UIPreferencesService.build_profile(legacy).visible_modules
