"""Consistent, monitor-aware geometry for NabiCode operational windows."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QTimer
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QFileDialog, QInputDialog,
    QMessageBox,
)


_APPLIED_PROPERTY = "nabicodeAdaptiveGeometryApplied"
_COMPACT_DIALOGS = (QMessageBox, QFileDialog, QColorDialog, QInputDialog)


class AdaptiveWindowPolicy(QObject):
    """Opens operational dialogs wide and inside the usable monitor area."""

    def __init__(self, application: QApplication) -> None:
        super().__init__(application)
        self.application = application
        application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if isinstance(watched, QComboBox) and event.type() == QEvent.Type.Wheel:
            view = watched.view()
            if view is None or not view.isVisible():
                event.ignore()
                return True
        if (
            isinstance(watched, QDialog)
            and not isinstance(watched, _COMPACT_DIALOGS)
            and event.type() == QEvent.Type.Show
            and not bool(watched.property(_APPLIED_PROPERTY))
        ):
            watched.setProperty(_APPLIED_PROPERTY, True)
            QTimer.singleShot(0, lambda window=watched: self._fit(window))
        return False

    def _fit(self, window: QDialog) -> None:
        if not window.isVisible():
            return
        screen = window.screen() or self.application.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = max(720, min(1400, int(available.width() * 0.94)))
        height = max(520, min(900, int(available.height() * 0.90)))
        width = min(width, available.width())
        height = min(height, available.height())
        window.resize(width, height)
        window.move(QPoint(
            available.x() + max(0, (available.width() - window.width()) // 2),
            available.y() + max(0, (available.height() - window.height()) // 2),
        ))


def install_adaptive_window_policy(application: QApplication) -> AdaptiveWindowPolicy:
    controller = getattr(application, "_nabicode_adaptive_window_policy", None)
    if controller is None:
        controller = AdaptiveWindowPolicy(application)
        application._nabicode_adaptive_window_policy = controller
    return controller
