"""Runtime-wide visual preferences without weakening semantic colours."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from services.ui_preferences import UIPreferencesService


_BASE_STYLE_PROPERTY = "nabicodeVisualBaseStyle"


class VisualThemeController(QObject):
    """Applies saved colours to existing and subsequently created Qt windows."""

    def __init__(self, application: QApplication) -> None:
        super().__init__(application)
        self.application = application
        self.values = UIPreferencesService.validate_visual({})
        application.installEventFilter(self)

    def update(self, values) -> dict:
        self.values = UIPreferencesService.validate_visual(values)
        palette = QPalette(self.application.palette())
        background = QColor(self.values["window_background"])
        button = QColor(self.values["common_button_background"])
        text = QColor(self.values["text_color"])
        focus = QColor(self.values["focus_color"])
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            palette.setColor(group, QPalette.ColorRole.Window, background)
            palette.setColor(group, QPalette.ColorRole.Base, background)
            palette.setColor(group, QPalette.ColorRole.AlternateBase, button)
            palette.setColor(group, QPalette.ColorRole.Button, button)
            palette.setColor(group, QPalette.ColorRole.WindowText, text)
            palette.setColor(group, QPalette.ColorRole.Text, text)
            palette.setColor(group, QPalette.ColorRole.ButtonText, text)
            palette.setColor(group, QPalette.ColorRole.Highlight, focus)
            palette.setColor(group, QPalette.ColorRole.HighlightedText, text)
        self.application.setPalette(palette)
        for widget in self.application.allWidgets():
            widget.setPalette(palette)
            if widget.isWindow():
                self._apply_window_override(widget)
        return dict(self.values)

    def eventFilter(self, watched, event) -> bool:
        if isinstance(watched, QWidget) and event.type() in {
            QEvent.Type.Polish, QEvent.Type.Show,
        }:
            watched.setPalette(self.application.palette())
            if watched.isWindow():
                self._apply_window_override(watched)
        return False

    def _apply_window_override(self, window: QWidget) -> None:
        base = window.property(_BASE_STYLE_PROPERTY)
        if base is None:
            base = window.styleSheet()
            window.setProperty(_BASE_STYLE_PROPERTY, base)
        safe = self.values
        # Generic selectors are appended after each window's local theme. More
        # specific semantic selectors (#primary, #warning, #checkout, etc.)
        # retain precedence and therefore keep operational meaning.
        override = f"""
            QDialog, QMainWindow {{
                background:{safe['window_background']}; color:{safe['text_color']};
            }}
            QLabel {{ color:{safe['text_color']}; }}
            QPushButton {{
                background:{safe['common_button_background']}; color:{safe['text_color']};
            }}
            QPushButton:focus {{ border:2px solid {safe['focus_color']}; }}
        """
        window.setStyleSheet(str(base) + override)


def apply_global_visual_preferences(values) -> dict:
    application = QApplication.instance()
    if application is None:
        return UIPreferencesService.validate_visual(values)
    controller = getattr(application, "_nabicode_visual_theme_controller", None)
    if controller is None:
        controller = VisualThemeController(application)
        application._nabicode_visual_theme_controller = controller
    return controller.update(values)
