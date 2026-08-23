from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class NabiActivationDialog(QDialog):
    """Coleta credenciais sem armazená-las no painel ou no histórico."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ativar Nabi")
        self.setModal(True)
        root = QVBoxLayout(self)
        explanation = QLabel(
            "A Nabi usa as permissões do usuário autenticado. "
            "A senha não será enviada ao modelo."
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setAccessibleName("Usuário para ativar a Nabi")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("Senha para ativar a Nabi")
        form.addRow("Usuário", self.username)
        form.addRow("Senha", self.password)
        root.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Ativar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @classmethod
    def get_credentials(cls, parent=None) -> tuple[str, str] | None:
        dialog = cls(parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.username.text(), dialog.password.text()

