from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout


class LegacySecurityMigrationDialog(QDialog):
    """Migração obrigatória de credencial para bases anteriores ao primeiro acesso."""

    def __init__(self, security, parent=None):
        super().__init__(parent)
        self.security = security
        self.setWindowTitle("Atualização de segurança do NabiCode")
        self.setModal(True)
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        title = QLabel("PROTEJA O ACESSO EXISTENTE")
        title.setStyleSheet("font-size:21px;font-weight:900;color:#d29922")
        root.addWidget(title)
        note = QLabel(
            "Esta base foi criada antes do novo controle de acesso. Informe um "
            "administrador existente e substitua sua senha antes de liberar os módulos."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        form = QFormLayout()
        self.username = QLineEdit("admin")
        self.current_password = QLineEdit()
        self.new_password = QLineEdit()
        self.confirmation = QLineEdit()
        for field in (self.current_password, self.new_password, self.confirmation):
            field.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Administrador existente*", self.username)
        form.addRow("Senha atual*", self.current_password)
        form.addRow("Nova senha*", self.new_password)
        form.addRow("Repita a nova senha*", self.confirmation)
        root.addLayout(form)
        self.finish = QPushButton("Atualizar segurança [Enter]")
        self.finish.clicked.connect(self.complete)
        root.addWidget(self.finish)
        self.fields = (self.username, self.current_password, self.new_password, self.confirmation, self.finish)
        for field in self.fields:
            field.installEventFilter(self)
        self.username.setFocus()

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
        if self.new_password.text() != self.confirmation.text():
            QMessageBox.warning(self, "Atualização de segurança", "As novas senhas não coincidem.")
            self.new_password.clear(); self.confirmation.clear(); self.new_password.setFocus()
            return
        try:
            self.security.complete_existing_installation_migration(
                username=self.username.text(), current_password=self.current_password.text(),
                new_password=self.new_password.text(),
            )
        except Exception as error:
            self.current_password.clear()
            QMessageBox.warning(self, "Atualização de segurança", str(error))
            self.current_password.setFocus()
            return
        self.current_password.clear(); self.new_password.clear(); self.confirmation.clear()
        QMessageBox.information(self, "Segurança atualizada", "A credencial antiga foi substituída. Entre novamente com a nova senha.")
        self.accept()
