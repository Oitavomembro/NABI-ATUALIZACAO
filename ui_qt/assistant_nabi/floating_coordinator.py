from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from shiboken6 import isValid

from .floating_host import NabiFloatingAssistant


OVERLAY_POLICY_PROPERTY = "nabiOverlayPolicy"
SAFE_POLICY = "normal"
SENSITIVE_POLICIES = frozenset({
    "sensitive", "critical", "login", "license", "activation", "fiscal", "destructive"
})


def classify_nabi_overlay(window: QWidget, policy: str) -> None:
    """Classifica a apresentação; não concede permissão nem capacidade."""

    normalized = str(policy).strip().lower()
    if normalized not in SENSITIVE_POLICIES | {SAFE_POLICY}:
        raise ValueError("Classificação de apresentação da Nabi inválida.")
    window.setProperty(OVERLAY_POLICY_PROPERTY, normalized)


class NabiFloatingCoordinator(QObject):
    """Mantém uma Nabi nas janelas seguras e respeita toda modalidade Qt."""

    def __init__(self, application: QApplication, root: QWidget, floating: NabiFloatingAssistant) -> None:
        super().__init__(root)
        self._application = application
        self._root = root
        self._floating = floating
        self._installed = True
        application.installEventFilter(self)

    def shutdown(self) -> None:
        """Remove o filtro global assim que o shell encerra."""

        if self._installed:
            self._application.removeEventFilter(self)
            self._installed = False
        floating = getattr(self, "_floating", None)
        if floating is not None and isValid(floating):
            floating.hide()

    @property
    def floating(self) -> NabiFloatingAssistant:
        return self._floating

    def eventFilter(self, watched, event) -> bool:
        root = getattr(self, "_root", None)
        application = getattr(self, "_application", None)
        floating = getattr(self, "_floating", None)
        if watched is root and event.type() == QEvent.Type.Destroy:
            self.shutdown()
            return False
        if watched is root and event.type() == QEvent.Type.Close:
            # O filtro recebe Close antes de QWidget.closeEvent decidir se o
            # fechamento será aceito. Confira no próximo ciclo para não
            # desmontar a Nabi quando uma janela recusar o encerramento.
            QTimer.singleShot(0, self._shutdown_if_root_closed)
            return False
        if floating is None or not isValid(floating):
            return False
        if (
            watched is floating.parentWidget()
            and watched is not root
            and event.type() in {QEvent.Type.Close, QEvent.Type.Hide, QEvent.Type.Destroy}
        ):
            # Recolhe antes que um diálogo com WA_DeleteOnClose possa destruir
            # junto a única instância do mascote.
            floating.attach_to(root)
        if isinstance(watched, QWidget) and event.type() in {
            QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Close,
            QEvent.Type.WindowActivate, QEvent.Type.WindowDeactivate,
            QEvent.Type.Resize, QEvent.Type.Move,
        }:
            QTimer.singleShot(0, self.refresh)
        return False

    def refresh(self) -> None:
        if (
            not self._installed
            or not isValid(self._root)
            or not isValid(self._floating)
        ):
            return
        if not self._root.isVisible():
            self._floating.hide()
            return
        modal = self._application.activeModalWidget()
        if modal is not None and self._belongs_to_root(modal):
            self._floating.hide()
            return
        active = self._application.activeWindow()
        if active is not None and self._belongs_to_root(active):
            if self._is_sensitive(active):
                self._floating.hide()
                return
            if isinstance(active, QDialog):
                if active.windowModality() != Qt.WindowModality.NonModal:
                    self._floating.hide()
                    return
                self._floating.attach_to(active)
                return
        self._floating.attach_to(self._root)

    def _shutdown_if_root_closed(self) -> None:
        if not self._installed or not isValid(self._root):
            return
        if not self._root.isVisible():
            self.shutdown()

    def _belongs_to_root(self, widget: QWidget) -> bool:
        current: QWidget | None = widget
        while current is not None:
            if current is self._root:
                return True
            current = current.parentWidget()
        return False

    @staticmethod
    def _is_sensitive(widget: QWidget) -> bool:
        policy = str(widget.property(OVERLAY_POLICY_PROPERTY) or "").strip().lower()
        return policy in SENSITIVE_POLICIES
