from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniversalLayoutMetrics:
    width: int
    height: int
    columns: int
    row_height: int = 38
    action_height: int = 42
    horizontal_padding: int = 18
    vertical_padding: int = 12


class UniversalLayoutPolicy:
    """Regras centralizadas para dimensões responsivas dos formulários.

    A política nunca devolve uma janela maior que a área útil informada. Em
    monitores menores que o mínimo de conforto, reduz a janela e força uma
    coluna, deixando o conteúdo acessível pela área rolável do formulário.
    """

    MIN_WIDTH = 720
    MIN_HEIGHT = 520
    ABSOLUTE_MIN_WIDTH = 360
    ABSOLUTE_MIN_HEIGHT = 320
    MAX_WIDTH_RATIO = 0.95
    MAX_HEIGHT_RATIO = 0.92

    @classmethod
    def metrics(
        cls,
        screen_width: int,
        screen_height: int,
        *,
        preferred_width: int = 1080,
        preferred_height: int = 720,
    ) -> UniversalLayoutMetrics:
        if screen_width <= 0 or screen_height <= 0:
            raise ValueError("As dimensões da tela devem ser positivas.")

        usable_width = max(1, int(screen_width * cls.MAX_WIDTH_RATIO))
        usable_height = max(1, int(screen_height * cls.MAX_HEIGHT_RATIO))
        minimum_width = min(cls.MIN_WIDTH, usable_width)
        minimum_height = min(cls.MIN_HEIGHT, usable_height)
        width = min(max(minimum_width, preferred_width), usable_width)
        height = min(max(minimum_height, preferred_height), usable_height)
        width = max(min(width, screen_width), min(cls.ABSOLUTE_MIN_WIDTH, screen_width))
        height = max(min(height, screen_height), min(cls.ABSOLUTE_MIN_HEIGHT, screen_height))

        columns = 1 if width < 860 else 2 if width < 1120 else 3
        return UniversalLayoutMetrics(width=width, height=height, columns=columns)

    @staticmethod
    def geometry(metrics: UniversalLayoutMetrics) -> str:
        return f"{metrics.width}x{metrics.height}"

    @classmethod
    def safe_minsize(cls, metrics: UniversalLayoutMetrics) -> tuple[int, int]:
        """Retorna um tamanho mínimo que não ultrapassa a janela calculada."""
        return min(cls.MIN_WIDTH, metrics.width), min(cls.MIN_HEIGHT, metrics.height)

    @staticmethod
    def field_position(index: int, columns: int, *, colspan: int = 1) -> tuple[int, int, int]:
        """Calcula linha, coluna e colspan seguros para formulários responsivos."""
        if index < 0:
            raise ValueError("O índice do campo não pode ser negativo.")
        if columns <= 0:
            raise ValueError("A quantidade de colunas deve ser positiva.")
        safe_colspan = max(1, min(int(colspan), columns))
        row = index // columns
        column = index % columns
        if column + safe_colspan > columns:
            row += 1
            column = 0
        return row, column, safe_colspan
