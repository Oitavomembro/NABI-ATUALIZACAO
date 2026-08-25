from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)
from .login_dialog import ADMIN_METALLIC_STYLE

STYLE = ADMIN_METALLIC_STYLE + "QDialog { font-size:14px; } QPushButton { min-height:74px; font-size:15px; text-align:left; }"


@dataclass(frozen=True, slots=True)
class AdministrativeModule:
    """Entrada segura do hub; identidade e permissão nunca vêm da GUI filha."""

    label: str
    description: str
    shortcut: str
    permission_module: str
    permission_action: str
    factory: Callable[[QWidget], QDialog]
    module_id: str = ""
    embedded_factory: Callable[[QWidget], QWidget] | None = None
    summary_loader: Callable[[], object] | None = None


class AdministrativeModuleHub(QDialog):
    """Menu administrativo Qt inspirado nos cartões operacionais do Legacy."""

    def __init__(self, security, modules: tuple[AdministrativeModule, ...], parent=None):
        super().__init__(parent)
        self.security = security
        self.modules = tuple(modules)
        self.setWindowTitle("Módulos NabiCode")
        self.resize(840, 520)
        self.setMinimumSize(680, 430)
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        title = QLabel("MÓDULOS DO NABICODE")
        title.setStyleSheet("font-size:25px;font-weight:900;color:#e4e8eb;border-bottom:1px solid #73c7dc")
        root.addWidget(title)
        self.identity = QLabel()
        self.identity.setStyleSheet("color:#aeb5bb;font-size:13px")
        root.addWidget(self.identity)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.buttons: list[QPushButton] = []
        self._module_by_button: dict[QPushButton, AdministrativeModule] = {}
        self._shortcuts: list[QShortcut] = []
        for index, module in enumerate(self.modules):
            button = QPushButton(
                f"{module.label}  [{module.shortcut}]\n{module.description}"
            )
            button.setAccessibleName(module.label)
            button.installEventFilter(self)
            button.clicked.connect(
                lambda _checked=False, selected=module: self.open_module(selected)
            )
            grid.addWidget(button, index // 2, index % 2)
            self.buttons.append(button)
            self._module_by_button[button] = module
            shortcut = QShortcut(QKeySequence(module.shortcut), self)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(
                lambda selected=module: self.open_module(selected)
            )
            self._shortcuts.append(shortcut)
        root.addLayout(grid, 1)
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.setAutoRepeat(False)
        self._escape.activated.connect(self.reject)
        self.refresh_identity()
        if self.buttons:
            self.buttons[0].setFocus(Qt.FocusReason.OtherFocusReason)

    def refresh_identity(self) -> None:
        session = getattr(self.security, "session", None)
        if session is None or self.security.is_expired():
            self.identity.setText("SESSÃO EXPIRADA — entre novamente para abrir módulos")
            return
        self.identity.setText(
            f"Operador: {session.user.display_name}  •  Perfil: {session.user.profile}"
        )

    def _authorized(self, module: AdministrativeModule) -> None:
        session = getattr(self.security, "session", None)
        if session is None or self.security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self.security.require(
            module.permission_module, module.permission_action
        ):
            raise PermissionError(
                f"Seu perfil não possui permissão para abrir {module.label}."
            )
        self.security.touch()

    def open_module(self, module: AdministrativeModule) -> bool:
        try:
            self._authorized(module)
            dialog = module.factory(self)
            if not isinstance(dialog, QDialog):
                raise TypeError("O módulo deve abrir uma janela Qt.")
            dialog.exec()
        except PermissionError as error:
            QMessageBox.warning(self, "Acesso negado", str(error))
            self.refresh_identity()
            return False
        except Exception as error:
            QMessageBox.warning(self, module.label, str(error))
            return False
        self.refresh_identity()
        return True

    def eventFilter(self, watched, event) -> bool:
        if (
            watched in self._module_by_button
            and event.type() == QEvent.Type.KeyPress
            and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
        ):
            event.accept()
            if event.isAutoRepeat():
                return True
            buttons = tuple(button for button in self.buttons if button.isEnabled())
            index = buttons.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                buttons[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            else:
                self.open_module(self._module_by_button[watched])
            return True
        return super().eventFilter(watched, event)
