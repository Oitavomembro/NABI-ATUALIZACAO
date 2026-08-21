"""Infraestrutura visual do NabiCode.

Este pacote não contém regras de negócio nem acesso a dados.
"""

from .background_manager import BackgroundManager, BackgroundSettings, RenderMetrics
from .layout_manager import LayoutManager, LayoutViewport
from .date_picker import open_date_picker
from .window_reveal import (
    prepare_hidden_toplevel,
    reveal_prepared_toplevel,
    reveal_prepared_toplevel_smooth,
    reveal_prepared_toplevel_when_idle,
)
from .theme import (
    DEFAULT_THEME,
    DEFAULT_THEME_MANAGER,
    NabiTheme,
    ThemeManager,
    apply_responsive_geometry,
    configure_ctk,
    configure_ttk,
)

__all__ = [
    "BackgroundManager",
    "BackgroundSettings",
    "RenderMetrics",
    "LayoutManager",
    "LayoutViewport",
    "open_date_picker",
    "prepare_hidden_toplevel",
    "reveal_prepared_toplevel",
    "reveal_prepared_toplevel_smooth",
    "reveal_prepared_toplevel_when_idle",
    "DEFAULT_THEME",
    "DEFAULT_THEME_MANAGER",
    "NabiTheme",
    "ThemeManager",
    "apply_responsive_geometry",
    "configure_ctk",
    "configure_ttk",
]
