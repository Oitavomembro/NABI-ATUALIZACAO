from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class InterfaceProfile:
    mode: str
    workspace: str
    density: str
    visible_modules: tuple[str, ...]


class UIPreferencesService:
    """Normaliza preferências visuais e calcula os módulos visíveis.

    A classe não depende de Tkinter, portanto pode ser testada isoladamente.
    """

    MODES = ("Simples", "Intermediário", "Avançado")
    WORKSPACES = ("Geral", "Caixa", "Estoque", "Financeiro", "Atendimento", "Gerência")
    DENSITIES = ("Compacta", "Normal", "Confortável")
    THEMES = ("Azul Profissional", "Claro Minimalista", "Escuro Profissional", "Verde Empresarial", "Grafite Executivo")
    BACKGROUND_SCALES = ("automática", "pequena", "média", "grande")
    BACKGROUND_POSITIONS = ("centro", "superior", "inferior")

    DASHBOARD_WIDGETS = {
        "resumo": "Resumo financeiro do dia",
        "cobrancas": "Cobranças em atraso",
        "produtos": "Resumo de produtos",
        "historico": "Histórico de movimentações",
    }

    WIDGET_ALIASES = {
        "vendas": "historico",
        "estoque": "produtos",
    }

    MODE_DEFAULT_WIDGETS = {
        "Simples": ("resumo", "cobrancas"),
        "Intermediário": ("resumo", "cobrancas", "produtos", "historico"),
        "Avançado": ("resumo", "cobrancas", "produtos", "historico"),
    }

    MODULE_LABELS = {
        "dashboard": "Início",
        "vendas": "Vendas",
        "clientes": "Clientes",
        "produtos": "Produtos",
        "financeiro": "Financeiro",
        "relatorios": "Relatórios",
        "configs": "Configurações",
    }
    MODULE_ORDER = tuple(MODULE_LABELS)

    DEFAULTS: dict[str, Any] = {
        "mode": "Intermediário",
        "workspace": "Geral",
        "density": "Normal",
        "theme": "Azul Profissional",
        "adaptive_menu": True,
        "custom_navigation": False,
        "navigation_modules": list(MODULE_ORDER),
        "dashboard_widgets": ["resumo", "cobrancas", "produtos", "historico"],
        "favorites": [],
        "background_enabled": True,
        "background_opacity": 0.10,
        "background_scale": "automática",
        "background_position": "centro",
    }

    MODE_MODULES = {
        "Simples": ("dashboard", "vendas", "clientes", "configs"),
        "Intermediário": ("dashboard", "vendas", "clientes", "produtos", "configs"),
        "Avançado": ("dashboard", "vendas", "clientes", "produtos", "financeiro", "relatorios", "configs"),
    }

    WORKSPACE_MODULES = {
        "Geral": ("dashboard", "vendas", "clientes", "produtos", "configs"),
        "Caixa": ("dashboard", "vendas", "clientes", "produtos", "configs"),
        "Estoque": ("dashboard", "produtos", "configs"),
        "Financeiro": ("dashboard", "clientes", "financeiro", "relatorios", "configs"),
        "Atendimento": ("dashboard", "clientes", "vendas", "configs"),
        "Gerência": ("dashboard", "vendas", "clientes", "produtos", "relatorios", "configs"),
    }

    ROW_HEIGHTS = {"Compacta": 22, "Normal": 27, "Confortável": 34}

    @classmethod
    def normalize(cls, values: Mapping[str, Any] | None) -> dict[str, Any]:
        data = deepcopy(cls.DEFAULTS)
        if isinstance(values, Mapping):
            data.update({key: deepcopy(value) for key, value in values.items() if key in data})

        if data["mode"] not in cls.MODES:
            data["mode"] = cls.DEFAULTS["mode"]
        if data["workspace"] not in cls.WORKSPACES:
            data["workspace"] = cls.DEFAULTS["workspace"]
        if data["density"] not in cls.DENSITIES:
            data["density"] = cls.DEFAULTS["density"]
        if data["theme"] not in cls.THEMES:
            data["theme"] = cls.DEFAULTS["theme"]
        data["adaptive_menu"] = bool(data["adaptive_menu"])
        data["custom_navigation"] = bool(data["custom_navigation"])
        data["background_enabled"] = bool(data["background_enabled"])
        try:
            opacity = float(data["background_opacity"])
        except (TypeError, ValueError):
            opacity = cls.DEFAULTS["background_opacity"]
        data["background_opacity"] = max(0.02, min(0.25, opacity))
        if data["background_scale"] not in cls.BACKGROUND_SCALES:
            data["background_scale"] = cls.DEFAULTS["background_scale"]
        if data["background_position"] not in cls.BACKGROUND_POSITIONS:
            data["background_position"] = cls.DEFAULTS["background_position"]

        navigation_modules = data.get("navigation_modules")
        if not isinstance(navigation_modules, list):
            navigation_modules = list(cls.MODULE_ORDER)
        normalized_modules = [
            module_id for module_id in cls.MODULE_ORDER
            if module_id in navigation_modules
        ]
        if not normalized_modules:
            normalized_modules = ["dashboard"]
        data["navigation_modules"] = normalized_modules

        widgets = data.get("dashboard_widgets")
        if not isinstance(widgets, list):
            widgets = list(cls.MODE_DEFAULT_WIDGETS[data["mode"]])
        normalized_widgets: list[str] = []
        for item in widgets:
            widget_id = cls.WIDGET_ALIASES.get(str(item).strip(), str(item).strip())
            if widget_id in cls.DASHBOARD_WIDGETS and widget_id not in normalized_widgets:
                normalized_widgets.append(widget_id)
        if not normalized_widgets:
            normalized_widgets = list(cls.MODE_DEFAULT_WIDGETS[data["mode"]])
        data["dashboard_widgets"] = normalized_widgets

        favorites = data.get("favorites")
        if not isinstance(favorites, list):
            favorites = []
        normalized_favorites: list[str] = []
        for item in favorites:
            module_id = str(item).strip()
            if module_id in cls.MODULE_LABELS and module_id not in normalized_favorites:
                normalized_favorites.append(module_id)
        data["favorites"] = normalized_favorites
        return data


    @staticmethod
    def user_key(username: str) -> str:
        """Normaliza a chave usada para separar preferências por usuário."""
        value = str(username or "").strip().casefold()
        if not value or any(ch.isspace() for ch in value):
            raise ValueError("Usuário inválido para preferências de interface.")
        return value

    @classmethod
    def build_profile(cls, values: Mapping[str, Any] | None) -> InterfaceProfile:
        data = cls.normalize(values)
        mode_modules = cls.MODE_MODULES[data["mode"]]
        if data["custom_navigation"]:
            selected = set(data["navigation_modules"])
            visible = tuple(module_id for module_id in cls.MODULE_ORDER if module_id in selected)
        elif not data["adaptive_menu"]:
            visible = mode_modules
        else:
            workspace_modules = set(cls.WORKSPACE_MODULES[data["workspace"]])
            visible = tuple(module for module in mode_modules if module in workspace_modules)
            if "configs" not in visible:
                visible += ("configs",)
            if "dashboard" not in visible:
                visible = ("dashboard",) + visible
        return InterfaceProfile(
            mode=data["mode"],
            workspace=data["workspace"],
            density=data["density"],
            visible_modules=visible,
        )

    @classmethod
    def row_height(cls, density: str) -> int:
        return cls.ROW_HEIGHTS.get(density, cls.ROW_HEIGHTS[cls.DEFAULTS["density"]])

    @classmethod
    def dashboard_widgets(cls, values: Mapping[str, Any] | None) -> tuple[str, ...]:
        """Retorna a ordem validada dos widgets visíveis do dashboard."""
        data = cls.normalize(values)
        return tuple(data["dashboard_widgets"])

    @classmethod
    def favorites(cls, values: Mapping[str, Any] | None) -> tuple[str, ...]:
        """Retorna favoritos válidos, únicos e na ordem persistida."""
        return tuple(cls.normalize(values)["favorites"])

    @classmethod
    def toggle_favorite(cls, values: Mapping[str, Any] | None, module_id: str) -> dict[str, Any]:
        """Adiciona ou remove um módulo dos favoritos sem alterar outras preferências."""
        if module_id not in cls.MODULE_LABELS:
            raise ValueError(f"Módulo desconhecido: {module_id}")
        data = cls.normalize(values)
        favorites = list(data["favorites"])
        if module_id in favorites:
            favorites.remove(module_id)
        else:
            favorites.append(module_id)
        data["favorites"] = favorites
        return data

    @classmethod
    def move_favorite(cls, values: Mapping[str, Any] | None, module_id: str, offset: int) -> dict[str, Any]:
        """Move um favorito uma posição para cima ou para baixo."""
        data = cls.normalize(values)
        favorites = list(data["favorites"])
        if module_id not in favorites or offset == 0:
            return data
        current = favorites.index(module_id)
        target = max(0, min(len(favorites) - 1, current + int(offset)))
        if target != current:
            favorites[current], favorites[target] = favorites[target], favorites[current]
        data["favorites"] = favorites
        return data
