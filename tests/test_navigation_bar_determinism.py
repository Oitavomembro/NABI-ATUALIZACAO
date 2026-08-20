from __future__ import annotations

from pathlib import Path

from core.config_manager import ConfigManager
from services.ui_preferences import UIPreferencesService


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_single_persistent_navigation_bar_is_not_recreated_by_screens():
    assert SOURCE.count("self.criar_cabecalho_e_botoes(") == 1
    assert "self.frame_navegacao_persistente" in SOURCE
    assert "self.container_conteudo_telas" in SOURCE
    assert "botao.pack_forget()" not in SOURCE


def test_switching_every_module_100_times_keeps_identical_buttons():
    profile = UIPreferencesService.build_profile({
        "mode": "Avançado",
        "workspace": "Financeiro",
        "adaptive_menu": True,
    })
    expected = UIPreferencesService.navigation_positions(profile.visible_modules)
    destinations = ("dashboard", "clientes", "produtos", "financeiro", "caixa", "fiscal")
    for _ in range(100):
        for _destination in destinations:
            assert UIPreferencesService.navigation_positions(profile.visible_modules) == expected


def test_finance_visibility_changes_only_with_profile_configuration():
    enabled = UIPreferencesService.build_profile({
        "mode": "Avançado", "workspace": "Financeiro", "adaptive_menu": True,
    })
    assert "financeiro" in enabled.visible_modules
    disabled = UIPreferencesService.build_profile({
        "custom_navigation": True,
        "navigation_modules": ["dashboard", "clientes", "produtos", "caixa", "fiscal"],
    })
    assert "financeiro" not in disabled.visible_modules


def test_all_modes_and_workspaces_have_stable_order_and_no_duplicate():
    for mode in UIPreferencesService.MODES:
        for workspace in UIPreferencesService.WORKSPACES:
            profile = UIPreferencesService.build_profile({"mode": mode, "workspace": workspace})
            first = UIPreferencesService.navigation_positions(profile.visible_modules)
            assert first == UIPreferencesService.navigation_positions(profile.visible_modules)
            assert len(first) == len({module_id for module_id, _row, _column in first})


def test_1280_layout_uses_second_row_instead_of_clipping_buttons():
    positions = UIPreferencesService.navigation_positions(UIPreferencesService.MODULE_ORDER, columns=5)
    assert len(positions) == len(UIPreferencesService.MODULE_ORDER)
    assert max(column for _module, _row, column in positions) == 4
    assert max(row for _module, row, _column in positions) == 1
    assert 'frame_centralizador.grid_columnconfigure(coluna, weight=1, uniform="navegacao_topo")' in SOURCE


def test_sidebar_open_or_closed_does_not_change_navigation_set():
    profile = UIPreferencesService.build_profile({"mode": "Avançado", "adaptive_menu": False})
    opened = UIPreferencesService.navigation_positions(profile.visible_modules, columns=5)
    closed = UIPreferencesService.navigation_positions(profile.visible_modules, columns=5)
    assert opened == closed


def test_custom_navigation_and_new_user_defaults_are_deterministic():
    default_data = UIPreferencesService.normalize(None)
    assert default_data["navigation_modules"] == list(UIPreferencesService.MODULE_ORDER)
    selected = UIPreferencesService.build_profile({
        "custom_navigation": True,
        "navigation_modules": ["financeiro", "dashboard", "fiscal"],
    })
    assert selected.visible_modules == ("dashboard", "financeiro", "caixa", "fiscal")


def test_restart_preserves_complete_navigation_configuration(tmp_path: Path):
    path = tmp_path / "config.json"
    manager = ConfigManager(path, defaults={"interface": UIPreferencesService.DEFAULTS})
    configured = UIPreferencesService.normalize({
        "mode": "Avançado",
        "workspace": "Financeiro",
        "adaptive_menu": False,
        "custom_navigation": True,
        "navigation_modules": ["dashboard", "financeiro", "caixa", "fiscal"],
    })
    manager.set("interface", configured)
    reloaded = ConfigManager(path, defaults={"interface": UIPreferencesService.DEFAULTS})
    assert UIPreferencesService.normalize(reloaded.get("interface")) == configured


def test_legacy_compras_preference_is_migrated_to_fiscal():
    normalized = UIPreferencesService.normalize({
        "custom_navigation": True,
        "navigation_modules": ["dashboard", "compras"],
        "favorites": ["compras"],
    })
    assert normalized["navigation_modules"] == ["dashboard", "fiscal"]
    assert normalized["favorites"] == ["fiscal"]
