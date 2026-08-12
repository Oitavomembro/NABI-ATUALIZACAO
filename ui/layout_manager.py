"""Políticas responsivas globais para a interface do NabiCode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class LayoutViewport:
    width: int
    height: int
    compact: bool
    horizontal_padding: int
    vertical_padding: int
    table_min_height: int


class LayoutManager:
    """Centraliza regras de expansão sem alterar widgets de negócio."""

    SUPPORTED_RESOLUTIONS = (
        (1024, 768), (1280, 720), (1366, 768), (1600, 900),
        (1920, 1080), (2560, 1440), (3840, 2160),
    )
    COMPACT_WIDTH = 1180
    COMPACT_HEIGHT = 760
    MIN_TABLE_HEIGHT = 180
    CLIENT_COLUMN_MINIMUMS = {
        "Ficha": 90,
        "Nome": 210,
        "Saldo": 135,
        "Limite": 105,
        "Telefone": 115,
        "CPF": 120,
        "Fav": 46,
    }
    CLIENT_COLUMN_WEIGHTS = {
        "Ficha": 0.0,
        "Nome": 4.0,
        "Saldo": 0.0,
        "Limite": 0.0,
        "Telefone": 1.5,
        "CPF": 1.5,
        "Fav": 0.0,
    }

    @classmethod
    def viewport(cls, width: int, height: int) -> LayoutViewport:
        if width <= 0 or height <= 0:
            raise ValueError("As dimensões da janela devem ser positivas.")
        compact = width < cls.COMPACT_WIDTH or height < cls.COMPACT_HEIGHT
        return LayoutViewport(
            width=int(width),
            height=int(height),
            compact=compact,
            horizontal_padding=10 if compact else 20,
            vertical_padding=4 if compact else 8,
            table_min_height=cls.MIN_TABLE_HEIGHT,
        )

    @staticmethod
    def configure_root(container: Any, *, content_row: int = 0, content_column: int = 0) -> None:
        container.grid_rowconfigure(content_row, weight=1)
        container.grid_columnconfigure(content_column, weight=1)

    @staticmethod
    def configure_vertical_shell(container: Any, *, expandable_row: int, columns: int = 1) -> None:
        for column in range(max(1, int(columns))):
            container.grid_columnconfigure(column, weight=1)
        container.grid_rowconfigure(expandable_row, weight=1)

    @classmethod
    def distribute_columns(
        cls,
        available_width: int,
        minimums: Mapping[str, int],
        weights: Mapping[str, float] | None = None,
    ) -> dict[str, int]:
        if available_width <= 0:
            raise ValueError("A largura disponível deve ser positiva.")
        mins = {name: max(1, int(value)) for name, value in minimums.items()}
        minimum_total = sum(mins.values())
        if available_width <= minimum_total:
            return mins
        weights = weights or {name: 1.0 for name in mins}
        positive = {name: max(0.0, float(weights.get(name, 0.0))) for name in mins}
        weight_total = sum(positive.values())
        if weight_total <= 0:
            return mins
        extra = available_width - minimum_total
        result = dict(mins)
        allocated = 0
        weighted_names = [name for name in mins if positive[name] > 0]
        for name in weighted_names[:-1]:
            addition = int(extra * positive[name] / weight_total)
            result[name] += addition
            allocated += addition
        if weighted_names:
            result[weighted_names[-1]] += extra - allocated
        return result

    @classmethod
    def client_columns(cls, available_width: int) -> dict[str, int]:
        return cls.distribute_columns(available_width, cls.CLIENT_COLUMN_MINIMUMS, cls.CLIENT_COLUMN_WEIGHTS)

    @staticmethod
    def needs_horizontal_scroll(available_width: int, column_widths: Mapping[str, int] | Iterable[int]) -> bool:
        widths = column_widths.values() if isinstance(column_widths, Mapping) else column_widths
        return sum(max(0, int(value)) for value in widths) > max(0, int(available_width))

    @classmethod
    def apply_treeview_columns(cls, tree: Any, widths: Mapping[str, int], *, stretch: Iterable[str] = ()) -> None:
        stretchable = set(stretch)
        for name, width in widths.items():
            tree.column(name, width=int(width), minwidth=int(width), stretch=name in stretchable)

    @classmethod
    def apply_client_treeview(cls, tree: Any, available_width: int) -> dict[str, int]:
        widths = cls.client_columns(available_width)
        cls.apply_treeview_columns(tree, widths, stretch={"Nome", "Telefone", "CPF"})
        return widths

    @classmethod
    def window_geometry(
        cls,
        screen_width: int,
        screen_height: int,
        *,
        preferred_width: int = 1100,
        preferred_height: int = 780,
        min_width: int = 840,
        min_height: int = 620,
    ) -> tuple[str, tuple[int, int]]:
        if screen_width <= 0 or screen_height <= 0:
            raise ValueError("As dimensões da tela devem ser positivas.")
        usable_width = max(360, int(screen_width * 0.94))
        usable_height = max(320, int(screen_height * 0.90))
        width = min(preferred_width, usable_width)
        height = min(preferred_height, usable_height)
        safe_min_width = min(min_width, width)
        safe_min_height = min(min_height, height)
        return f"{width}x{height}", (safe_min_width, safe_min_height)
