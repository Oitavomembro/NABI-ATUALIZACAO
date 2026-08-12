"""Infraestrutura visual centralizada do NabiCode.

Este módulo contém somente tokens e configuração de componentes visuais. Não
acessa banco, serviços, impressão, PDV, pesquisa ou regras de negócio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NabiTheme:
    """Tokens imutáveis usados por toda a interface."""

    background: str = "#0d1117"
    surface: str = "#161b22"
    surface_elevated: str = "#21262d"
    border: str = "#30363d"
    text: str = "#ffffff"
    text_muted: str = "#c9d1d9"
    text_subtle: str = "#8b949e"
    disabled: str = "#484f58"
    disabled_text: str = "#8b949e"
    accent: str = "#00FF88"
    accent_hover: str = "#00cc6a"
    success: str = "#2ea043"
    warning: str = "#bf8700"
    danger: str = "#da3633"
    info: str = "#1f6feb"
    font_family: str = "Segoe UI"
    font_size_small: int = 10
    font_size_body: int = 12
    font_size_subtitle: int = 14
    font_size_title: int = 20
    radius_small: int = 6
    radius_medium: int = 8
    radius_large: int = 10
    spacing_xsmall: int = 4
    spacing_small: int = 6
    spacing_medium: int = 12
    spacing_large: int = 20
    button_height: int = 36
    input_height: int = 36
    table_row_height: int = 28
    scrollbar_width: int = 12
    border_width: int = 1
    tab_height: int = 34
    control_width: int = 180
    min_width: int = 1050
    min_height: int = 680
    preferred_width: int = 1220
    preferred_height: int = 780


DEFAULT_THEME = NabiTheme()


class ThemeManager:
    """Ponto único de configuração visual para CTk, ttk e Tk.

    Os métodos que retornam dicionários não importam bibliotecas gráficas. Isso
    mantém a infraestrutura testável em ambientes sem ``customtkinter`` ou sem
    servidor gráfico.
    """

    _BUTTON_VARIANTS: Mapping[str, tuple[str, str, str]] = {
        "primary": ("accent", "accent_hover", "background"),
        "secondary": ("surface_elevated", "border", "text"),
        "success": ("success", "accent_hover", "text"),
        "danger": ("danger", "border", "text"),
        "info": ("info", "border", "text"),
        "ghost": ("surface", "surface_elevated", "text"),
    }
    _COMPONENT_FACTORIES: Mapping[str, str] = {
        "button": "button_options",
        "frame": "frame_options",
        "label": "label_options",
        "entry": "entry_options",
        "combobox": "combobox_options",
        "optionmenu": "optionmenu_options",
        "textbox": "textbox_options",
        "checkbox": "checkbox_options",
        "radiobutton": "radiobutton_options",
        "switch": "switch_options",
        "slider": "slider_options",
        "progressbar": "progressbar_options",
        "scrollableframe": "scrollable_frame_options",
        "tabview": "tabview_options",
        "scrollbar": "scrollbar_options",
    }

    def __init__(self, theme: NabiTheme = DEFAULT_THEME) -> None:
        self.theme = theme

    @staticmethod
    def _apply_overrides(options: dict[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
        """Aplica customizações locais sem duplicar o padrão ``dict.update``."""
        options.update(overrides)
        return options

    @staticmethod
    def _normalize_component_name(component: str) -> str:
        return component.replace("_", "").replace("-", "").strip().lower()

    def _text_control_options(self) -> dict[str, Any]:
        """Base visual única para entradas textuais CTk."""
        return {
            "corner_radius": self.theme.radius_medium,
            "fg_color": self.theme.surface,
            "border_width": self.theme.border_width,
            "border_color": self.theme.border,
            "text_color": self.theme.text,
            "font": self.font_spec("body"),
        }

    def _selection_control_options(self) -> dict[str, Any]:
        """Base visual única para controles selecionáveis CTk."""
        return {
            "fg_color": self.theme.accent,
            "hover_color": self.theme.accent_hover,
            "border_color": self.theme.border,
            "text_color": self.theme.text,
            "font": self.font_spec("body"),
        }

    def font_spec(self, role: str = "body", *, weight: str | None = None) -> tuple[str, int, str]:
        sizes = {
            "small": self.theme.font_size_small,
            "body": self.theme.font_size_body,
            "subtitle": self.theme.font_size_subtitle,
            "title": self.theme.font_size_title,
        }
        normalized_role = role if role in sizes else "body"
        normalized_weight = weight or ("bold" if normalized_role in {"title", "subtitle"} else "normal")
        return self.theme.font_family, sizes[normalized_role], normalized_weight

    def font(self, role: str = "body", *, weight: str | None = None) -> Any:
        import customtkinter as ctk

        family, size, resolved_weight = self.font_spec(role, weight=weight)
        return ctk.CTkFont(family=family, size=size, weight=resolved_weight)

    def configure_ctk(self, *, appearance: str = "Dark") -> None:
        import customtkinter as ctk

        normalized = appearance if appearance in {"Dark", "Light", "System"} else "Dark"
        ctk.set_appearance_mode(normalized)
        ctk.set_default_color_theme("green")

    def button_options(self, variant: str = "primary", **overrides: Any) -> dict[str, Any]:
        normalized = variant if variant in self._BUTTON_VARIANTS else "primary"
        fg_name, hover_name, text_name = self._BUTTON_VARIANTS[normalized]
        options = {
            "height": self.theme.button_height,
            "corner_radius": self.theme.radius_medium,
            "fg_color": getattr(self.theme, fg_name),
            "hover_color": getattr(self.theme, hover_name),
            "text_color": getattr(self.theme, text_name),
            "font": self.font_spec("body", weight="bold"),
            "border_width": 1 if normalized in {"secondary", "ghost"} else 0,
            "border_color": self.theme.border,
        }
        return self._apply_overrides(options, overrides)

    def frame_options(self, *, elevated: bool = False, **overrides: Any) -> dict[str, Any]:
        options = {
            "corner_radius": self.theme.radius_large,
            "fg_color": self.theme.surface_elevated if elevated else self.theme.surface,
            "border_width": self.theme.border_width,
            "border_color": self.theme.border,
        }
        return self._apply_overrides(options, overrides)

    def label_options(
        self,
        role: str = "body",
        *,
        muted: bool = False,
        **overrides: Any,
    ) -> dict[str, Any]:
        options = {
            "text_color": self.theme.text_muted if muted else self.theme.text,
            "font": self.font_spec(role),
            "anchor": "w",
        }
        return self._apply_overrides(options, overrides)

    def entry_options(self, **overrides: Any) -> dict[str, Any]:
        options = self._text_control_options()
        options.update({
            "height": self.theme.input_height,
            "placeholder_text_color": self.theme.text_subtle,
        })
        return self._apply_overrides(options, overrides)

    def combobox_options(self, **overrides: Any) -> dict[str, Any]:
        options = self.entry_options()
        options.update({
            "button_color": self.theme.surface_elevated,
            "button_hover_color": self.theme.border,
            "dropdown_fg_color": self.theme.surface_elevated,
            "dropdown_hover_color": self.theme.border,
            "dropdown_text_color": self.theme.text,
        })
        return self._apply_overrides(options, overrides)

    def optionmenu_options(self, **overrides: Any) -> dict[str, Any]:
        options = self.combobox_options()
        options.pop("border_width", None)
        options.pop("border_color", None)
        options.update({
            "width": self.theme.control_width,
            "dynamic_resizing": False,
        })
        return self._apply_overrides(options, overrides)

    def radiobutton_options(self, **overrides: Any) -> dict[str, Any]:
        return self._apply_overrides(self._selection_control_options(), overrides)

    def switch_options(self, **overrides: Any) -> dict[str, Any]:
        options = {
            "fg_color": self.theme.border,
            "progress_color": self.theme.accent,
            "button_color": self.theme.text_muted,
            "button_hover_color": self.theme.text,
            "text_color": self.theme.text,
            "font": self.font_spec("body"),
        }
        return self._apply_overrides(options, overrides)

    def slider_options(self, **overrides: Any) -> dict[str, Any]:
        options = {
            "fg_color": self.theme.border,
            "progress_color": self.theme.accent,
            "button_color": self.theme.accent,
            "button_hover_color": self.theme.accent_hover,
        }
        return self._apply_overrides(options, overrides)

    def progressbar_options(self, **overrides: Any) -> dict[str, Any]:
        options = {
            "height": self.theme.spacing_medium,
            "corner_radius": self.theme.radius_small,
            "fg_color": self.theme.border,
            "progress_color": self.theme.accent,
        }
        return self._apply_overrides(options, overrides)

    def scrollable_frame_options(self, **overrides: Any) -> dict[str, Any]:
        options = self.frame_options()
        options.update({
            "scrollbar_fg_color": self.theme.surface,
            "scrollbar_button_color": self.theme.border,
            "scrollbar_button_hover_color": self.theme.text_subtle,
            "label_text_color": self.theme.text,
            "label_font": self.font_spec("subtitle"),
        })
        return self._apply_overrides(options, overrides)

    def component_options(
        self,
        component: str,
        **overrides: Any,
    ) -> dict[str, Any]:
        """Resolve opções visuais por nome sem duplicar seleção em telas."""
        normalized = self._normalize_component_name(component)
        method_name = self._COMPONENT_FACTORIES.get(normalized)
        if method_name is None:
            raise ValueError(f"Componente visual desconhecido: {component}")
        factory = getattr(self, method_name)
        return factory(**overrides)

    def textbox_options(self, **overrides: Any) -> dict[str, Any]:
        options = self._text_control_options()
        options.update({
            "scrollbar_button_color": self.theme.border,
            "scrollbar_button_hover_color": self.theme.text_subtle,
        })
        return self._apply_overrides(options, overrides)

    def checkbox_options(self, **overrides: Any) -> dict[str, Any]:
        options = self._selection_control_options()
        options["corner_radius"] = self.theme.radius_small
        return self._apply_overrides(options, overrides)

    def tabview_options(self, **overrides: Any) -> dict[str, Any]:
        options = {
            "height": self.theme.tab_height,
            "corner_radius": self.theme.radius_large,
            "fg_color": self.theme.surface,
            "border_width": self.theme.border_width,
            "border_color": self.theme.border,
            "segmented_button_fg_color": self.theme.surface_elevated,
            "segmented_button_selected_color": self.theme.accent_hover,
            "segmented_button_selected_hover_color": self.theme.accent,
            "segmented_button_unselected_color": self.theme.surface_elevated,
            "segmented_button_unselected_hover_color": self.theme.border,
            "text_color": self.theme.text,
        }
        return self._apply_overrides(options, overrides)

    def menu_options(self, **overrides: Any) -> dict[str, Any]:
        options = {
            "background": self.theme.surface_elevated,
            "foreground": self.theme.text,
            "activebackground": self.theme.accent_hover,
            "activeforeground": self.theme.text,
            "relief": "flat",
            "borderwidth": 0,
            "font": self.font_spec("body"),
        }
        return self._apply_overrides(options, overrides)

    def scrollbar_options(self, **overrides: Any) -> dict[str, Any]:
        options = {
            "width": self.theme.scrollbar_width,
            "corner_radius": self.theme.radius_small,
            "fg_color": self.theme.surface,
            "button_color": self.theme.border,
            "button_hover_color": self.theme.text_subtle,
        }
        return self._apply_overrides(options, overrides)

    def configure_ttk(
        self,
        style: Any,
        *,
        row_height: int | None = None,
        selected_color: str | None = None,
    ) -> None:
        """Padroniza tabelas, cabeçalhos e scrollbars ttk."""
        theme = self.theme
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=theme.surface,
            foreground=theme.text,
            fieldbackground=theme.surface,
            bordercolor=theme.border,
            lightcolor=theme.border,
            darkcolor=theme.border,
            rowheight=max(24, int(row_height or theme.table_row_height)),
            font=self.font_spec("small"),
        )
        style.configure(
            "Treeview.Heading",
            background=theme.surface_elevated,
            foreground=theme.text,
            bordercolor=theme.border,
            relief="flat",
            font=self.font_spec("small", weight="bold"),
        )
        style.configure(
            "Vertical.TScrollbar",
            background=theme.border,
            troughcolor=theme.surface,
            bordercolor=theme.surface,
            arrowcolor=theme.text_muted,
            width=theme.scrollbar_width,
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=theme.border,
            troughcolor=theme.surface,
            bordercolor=theme.surface,
            arrowcolor=theme.text_muted,
            width=theme.scrollbar_width,
        )
        style.map(
            "Treeview",
            background=[("selected", selected_color or theme.accent_hover)],
            foreground=[("selected", theme.text)],
        )
        style.map("Treeview.Heading", background=[("active", theme.border)])

    def apply_responsive_geometry(self, window: Any) -> str:
        """Dimensiona a janela sem ultrapassar a área útil da tela."""
        theme = self.theme
        screen_width = max(theme.min_width, int(window.winfo_screenwidth()))
        screen_height = max(theme.min_height, int(window.winfo_screenheight()))
        width = min(theme.preferred_width, max(theme.min_width, screen_width - 80))
        height = min(theme.preferred_height, max(theme.min_height, screen_height - 100))
        geometry = f"{width}x{height}"
        window.geometry(geometry)
        window.minsize(theme.min_width, theme.min_height)
        return geometry


DEFAULT_THEME_MANAGER = ThemeManager()


# Adaptadores mantidos para compatibilidade com o legado existente.
def configure_ctk(*, appearance: str = "Dark") -> None:
    DEFAULT_THEME_MANAGER.configure_ctk(appearance=appearance)


def configure_ttk(
    style: Any,
    *,
    theme: NabiTheme = DEFAULT_THEME,
    row_height: int = DEFAULT_THEME.table_row_height,
    selected_color: str | None = None,
) -> None:
    ThemeManager(theme).configure_ttk(
        style,
        row_height=row_height,
        selected_color=selected_color,
    )


def apply_responsive_geometry(window: Any, *, theme: NabiTheme = DEFAULT_THEME) -> str:
    return ThemeManager(theme).apply_responsive_geometry(window)
