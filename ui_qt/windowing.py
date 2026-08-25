from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


PRIMARY_WINDOW_CONTROLS = (
    Qt.WindowType.Window
    | Qt.WindowType.WindowTitleHint
    | Qt.WindowType.WindowSystemMenuHint
    | Qt.WindowType.WindowMinimizeButtonHint
    | Qt.WindowType.WindowMaximizeButtonHint
    | Qt.WindowType.WindowCloseButtonHint
)


def enable_primary_window_controls(window: QWidget) -> None:
    """Mantém a janela principal com os controles nativos do Windows."""

    window.setWindowFlags(window.windowFlags() | PRIMARY_WINDOW_CONTROLS)
