"""Consistent, monitor-aware geometry for NabiCode operational windows."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
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
            and watched.isWindow()
            and event.type() in {QEvent.Type.Polish, QEvent.Type.Show}
            and not bool(watched.property(_APPLIED_PROPERTY))
        ):
            watched.setProperty(_APPLIED_PROPERTY, True)
            self._prepare_before_first_paint(watched)
        return False

    def _prepare_before_first_paint(self, window: QDialog) -> None:
        """Define o estado final antes de o Windows compor o primeiro quadro.

        O fluxo antigo esperava o ``Show`` e agendava um resize para o ciclo
        seguinte. Isso tornava visível uma janela pequena, seguida de flash e
        maximização. A política agora é síncrona e única para toda janela
        operacional; diálogos compactos continuam fora dela.
        """
        if window.isFullScreen():
            return
        window.setWindowState(
            window.windowState() | Qt.WindowState.WindowMaximized
        )


def install_adaptive_window_policy(application: QApplication) -> AdaptiveWindowPolicy:
    controller = getattr(application, "_nabicode_adaptive_window_policy", None)
    if controller is None:
        controller = AdaptiveWindowPolicy(application)
        application._nabicode_adaptive_window_policy = controller
    return controller
