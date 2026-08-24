from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)


class InitialSetupDialog(QDialog):
    """Primeiro acesso restrito; não oferece nenhum módulo operacional."""

    def __init__(self, security, parent=None):
        super().__init__(parent)
        self.security = security
        self.setWindowTitle("Configuração inicial do NabiCode")
        self.setModal(True)
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        title = QLabel("PRIMEIRO ACESSO")
        title.setStyleSheet("font-size:22px;font-weight:900;color:#00d084")
        root.addWidget(title)
        note = QLabel(
            "Configure a empresa e crie o primeiro administrador. "
            "Nenhuma venda, operação financeira ou fiscal será liberada antes da conclusão."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        form = QFormLayout()
        self.store_name = QLineEdit()
        self.document = QLineEdit(); self.document.setMaxLength(18)
        self.email = QLineEdit(); self.email.setMaxLength(160)
        self.username = QLineEdit("admin"); self.username.setMaxLength(60)
        self.display_name = QLineEdit("Administrador"); self.display_name.setMaxLength(120)
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirmation = QLineEdit(); self.password_confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        for label, field in (
            ("Empresa/loja*", self.store_name), ("CNPJ", self.document),
            ("E-mail", self.email), ("Usuário administrador*", self.username),
            ("Nome do administrador*", self.display_name), ("Senha*", self.password),
            ("Repita a senha*", self.password_confirmation),
        ):
            form.addRow(label, field)
        root.addLayout(form)
        self.finish = QPushButton("Concluir configuração [Enter]")
        self.finish.setStyleSheet("background:#238636;color:white;min-height:38px;font-weight:800")
        self.finish.clicked.connect(self.complete)
        root.addWidget(self.finish)
        self.fields = (
            self.store_name, self.document, self.email, self.username,
            self.display_name, self.password, self.password_confirmation, self.finish,
        )
        for field in self.fields:
            field.installEventFilter(self)
        self.store_name.setFocus()

    def eventFilter(self, watched, event):
        if watched in self.fields and event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            if event.isAutoRepeat():
                return True
            index = self.fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.fields[max(0, index - 1)].setFocus()
            elif watched is self.finish:
                self.complete()
            else:
                self.fields[index + 1].setFocus()
            return True
        return super().eventFilter(watched, event)

    def complete(self) -> None:
        if self.password.text() != self.password_confirmation.text():
            QMessageBox.warning(self, "Configuração inicial", "As senhas não coincidem.")
            self.password.clear(); self.password_confirmation.clear(); self.password.setFocus()
            return
        try:
            self.security.complete_initial_setup(
                username=self.username.text(), display_name=self.display_name.text(),
                password=self.password.text(), store_name=self.store_name.text(),
                document=self.document.text(), email=self.email.text(),
            )
        except Exception as error:
            QMessageBox.warning(self, "Configuração inicial", str(error))
            return
        self.password.clear(); self.password_confirmation.clear()
        QMessageBox.information(
            self, "Configuração concluída",
            "Primeiro administrador criado. Agora entre com o usuário e a senha definidos.",
        )
        self.accept()
