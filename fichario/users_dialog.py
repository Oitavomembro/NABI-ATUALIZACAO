from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QMessageBox, QAbstractItemView,
)
from ui_qt.commercial.customer_dialog import STYLE


class AccountDialog(QDialog):
    def __init__(self, security, user=None, *, setup=False, parent=None):
        super().__init__(parent)
        self.security, self.user, self.setup = security, user, setup
        self.setWindowTitle("Primeiro acesso — administrador" if setup else "Cadastro de usuário")
        self.setStyleSheet(STYLE)
        self.resize(620, 480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit(user.username if user else "")
        self.username.setReadOnly(user is not None)
        self.name = QLineEdit(user.display_name if user else "")
        self.password = QLineEdit()
        self.confirm = QLineEdit()
        for field in (self.password, self.confirm):
            field.setEchoMode(QLineEdit.EchoMode.Password)
        self.profile = QComboBox()
        self.profile.addItems(("ADMIN",) if setup else ("OPERADOR", "GERENTE", "ADMIN"))
        if user:
            self.profile.setCurrentText(user.profile)
        self.active = QCheckBox("Usuário ativo")
        self.active.setChecked(user.active if user else True)
        for label, field in (("Login", self.username), ("Nome", self.name),
                             ("Senha (mínimo 6 caracteres)", self.password),
                             ("Repita a senha", self.confirm), ("Perfil", self.profile)):
            form.addRow(label, field)
        layout.addLayout(form)
        if not setup:
            layout.addWidget(self.active)
        save = QPushButton("Salvar usuário")
        save.setAutoDefault(False)
        save.clicked.connect(self.save)
        layout.addWidget(save)
        close = QPushButton("Cancelar")
        close.setAutoDefault(False)
        close.clicked.connect(self.reject)
        layout.addWidget(close)

    def save(self):
        try:
            if self.password.text() != self.confirm.text():
                raise ValueError("As senhas não coincidem.")
            if self.setup:
                self.security.setup_admin(self.username.text(), self.name.text(), self.password.text())
            else:
                self.security.save_account(
                    self.username.text(), self.name.text(), self.password.text(),
                    self.profile.currentText(), self.active.isChecked(),
                    existing=self.user is not None,
                )
        except Exception as error:
            QMessageBox.warning(self, "Usuário", str(error))
            return
        self.accept()


class UsersDialog(QDialog):
    def __init__(self, security, parent=None):
        super().__init__(parent)
        self.security = security
        self.setWindowTitle("Usuários do Fichário")
        self.setStyleSheet(STYLE)
        self.resize(850, 570)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Login", "Nome", "Perfil", "Ativo"))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        for label, action in (("Novo usuário", self.create), ("Editar / desativar selecionado", self.edit),
                              ("Fechar", self.reject)):
            button = QPushButton(label)
            button.setAutoDefault(False)
            button.clicked.connect(action)
            layout.addWidget(button)
        self.reload()

    def reload(self):
        self.security.actor("usuarios", "edit")
        self.users = self.security.list_users()
        self.table.setRowCount(len(self.users))
        for row, user in enumerate(self.users):
            for column, value in enumerate((user.username, user.display_name, user.profile,
                                            "Sim" if user.active else "Não")):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    def create(self):
        AccountDialog(self.security, parent=self).exec()
        self.reload()

    def edit(self):
        row = self.table.currentRow()
        if row >= 0:
            AccountDialog(self.security, self.users[row], parent=self).exec()
            self.reload()
