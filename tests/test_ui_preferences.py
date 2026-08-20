import unittest

from services.ui_preferences import UIPreferencesService


class UIPreferencesServiceTests(unittest.TestCase):
    def test_invalid_values_are_normalized(self):
        data = UIPreferencesService.normalize({
            "mode": "desconhecido",
            "workspace": "x",
            "density": "gigante",
            "theme": "qualquer",
            "favorites": "não é lista",
        })
        self.assertEqual(data["mode"], "Intermediário")
        self.assertEqual(data["workspace"], "Geral")
        self.assertEqual(data["density"], "Normal")
        self.assertEqual(data["theme"], "Azul Profissional")
        self.assertEqual(data["favorites"], [])

    def test_simple_mode_hides_advanced_modules(self):
        profile = UIPreferencesService.build_profile({"mode": "Simples", "workspace": "Geral"})
        self.assertEqual(profile.visible_modules, ("dashboard", "vendas", "clientes", "caixa", "configs"))
        self.assertNotIn("produtos", profile.visible_modules)

    def test_stock_workspace_restricts_navigation(self):
        profile = UIPreferencesService.build_profile({
            "mode": "Avançado",
            "workspace": "Estoque",
            "adaptive_menu": True,
        })
        self.assertEqual(profile.visible_modules, ("dashboard", "produtos", "caixa", "fiscal", "configs"))

    def test_non_adaptive_menu_uses_mode_only(self):
        profile = UIPreferencesService.build_profile({
            "mode": "Intermediário",
            "workspace": "Financeiro",
            "adaptive_menu": False,
        })
        self.assertIn("vendas", profile.visible_modules)
        self.assertIn("produtos", profile.visible_modules)

    def test_density_row_heights(self):
        self.assertLess(UIPreferencesService.row_height("Compacta"), UIPreferencesService.row_height("Normal"))
        self.assertLess(UIPreferencesService.row_height("Normal"), UIPreferencesService.row_height("Confortável"))

    def test_dashboard_widgets_are_normalized_and_aliased(self):
        data = UIPreferencesService.normalize({
            "dashboard_widgets": ["resumo", "vendas", "estoque", "desconhecido", "resumo"],
        })
        self.assertEqual(data["dashboard_widgets"], ["resumo", "historico", "produtos"])

    def test_dashboard_widgets_fallback_by_mode(self):
        data = UIPreferencesService.normalize({"mode": "Simples", "dashboard_widgets": []})
        self.assertEqual(
            tuple(data["dashboard_widgets"]),
            UIPreferencesService.MODE_DEFAULT_WIDGETS["Simples"],
        )

    def test_custom_navigation_uses_exact_selected_modules(self):
        profile = UIPreferencesService.build_profile({
            "custom_navigation": True,
            "navigation_modules": ["produtos", "vendas"],
            "mode": "Simples",
            "workspace": "Financeiro",
        })
        self.assertEqual(profile.visible_modules, ("vendas", "produtos", "caixa"))

    def test_custom_navigation_removes_unknown_and_duplicate_modules(self):
        data = UIPreferencesService.normalize({
            "custom_navigation": True,
            "navigation_modules": ["produtos", "desconhecido", "produtos", "clientes"],
        })
        self.assertEqual(data["navigation_modules"], ["clientes", "produtos"])

    def test_custom_navigation_falls_back_to_dashboard_when_empty(self):
        profile = UIPreferencesService.build_profile({
            "custom_navigation": True,
            "navigation_modules": [],
        })
        self.assertEqual(profile.visible_modules, ("dashboard", "caixa"))

    def test_cash_module_is_visible_in_every_interface_profile(self):
        for mode in UIPreferencesService.MODES:
            for workspace in UIPreferencesService.WORKSPACES:
                profile = UIPreferencesService.build_profile({"mode": mode, "workspace": workspace})
                self.assertIn("caixa", profile.visible_modules, (mode, workspace))

    def test_legacy_saved_navigation_cannot_hide_cash_module(self):
        profile = UIPreferencesService.build_profile({
            "custom_navigation": True,
            "navigation_modules": ["dashboard", "vendas", "clientes", "produtos", "configs"],
        })
        self.assertIn("caixa", profile.visible_modules)

    def test_favorites_remove_unknown_and_duplicate_modules(self):
        data = UIPreferencesService.normalize({
            "favorites": ["produtos", "desconhecido", "produtos", "dashboard"],
        })
        self.assertEqual(data["favorites"], ["produtos", "dashboard"])

    def test_toggle_favorite_adds_and_removes_module(self):
        added = UIPreferencesService.toggle_favorite({"favorites": ["dashboard"]}, "produtos")
        self.assertEqual(added["favorites"], ["dashboard", "produtos"])
        removed = UIPreferencesService.toggle_favorite(added, "dashboard")
        self.assertEqual(removed["favorites"], ["produtos"])

    def test_user_key_is_case_insensitive_and_rejects_whitespace(self):
        self.assertEqual(UIPreferencesService.user_key("  ADMIN  "), "admin")
        with self.assertRaises(ValueError):
            UIPreferencesService.user_key("usuario com espaço")

    def test_finance_module_can_be_favorited(self):
        data = UIPreferencesService.toggle_favorite({}, "financeiro")
        self.assertEqual(data["favorites"], ["financeiro"])

    def test_move_favorite_preserves_bounds_and_order(self):
        data = {"favorites": ["dashboard", "clientes", "produtos"]}
        moved = UIPreferencesService.move_favorite(data, "produtos", -1)
        self.assertEqual(moved["favorites"], ["dashboard", "produtos", "clientes"])
        unchanged = UIPreferencesService.move_favorite(moved, "dashboard", -1)
        self.assertEqual(unchanged["favorites"], ["dashboard", "produtos", "clientes"])


if __name__ == "__main__":
    unittest.main()


def test_background_preferences_are_persistable_and_normalized():
    data = UIPreferencesService.normalize({
        "background_enabled": 0,
        "background_opacity": 0.14,
        "background_scale": "grande",
        "background_position": "inferior",
    })
    assert data["background_enabled"] is False
    assert data["background_opacity"] == 0.14
    assert data["background_scale"] == "grande"
    assert data["background_position"] == "inferior"


def test_background_preferences_reject_unsafe_values():
    data = UIPreferencesService.normalize({
        "background_opacity": 5,
        "background_scale": "gigante",
        "background_position": "lateral",
    })
    assert data["background_opacity"] == 0.25
    assert data["background_scale"] == "automática"
    assert data["background_position"] == "centro"


def test_background_preferences_survive_config_manager_reload(tmp_path):
    from core.config_manager import ConfigManager

    path = tmp_path / "config.json"
    manager = ConfigManager(path, defaults={"interface": UIPreferencesService.DEFAULTS})
    configured = UIPreferencesService.normalize({
        "background_enabled": False,
        "background_opacity": 0.08,
        "background_scale": "pequena",
        "background_position": "superior",
    })
    manager.set("interface", configured)

    reloaded = ConfigManager(path, defaults={"interface": UIPreferencesService.DEFAULTS})
    assert reloaded.get("interface.background_enabled") is False
    assert reloaded.get("interface.background_opacity") == 0.08
    assert reloaded.get("interface.background_scale") == "pequena"
    assert reloaded.get("interface.background_position") == "superior"
