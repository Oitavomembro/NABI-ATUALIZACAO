from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from administration.user_application_service import UserDraft


STYLE = """
QDialog { background:#0d1117; color:#f0f6fc; font-size:14px; }
QLabel { color:#f0f6fc; }
QLineEdit,QComboBox,QTableWidget { background:#161b22;color:#f0f6fc;
 border:1px solid #30363d;border-radius:6px;min-height:38px; }
QPushButton { background:#30363d;color:#f0f6fc;border:0;border-radius:6px;
 min-height:40px;padding:0 14px;font-weight:700; }
QPushButton#primary { background:#238636; }
"""


class UserEditorDialog(QDialog):
    def __init__(self, application, user=None, parent=None) -> None:
        super().__init__(parent)
        self.application = application; self.user = user; self.saved = None
        self.setWindowTitle("Editar usuário" if user else "Novo usuário")
        self.setMinimumWidth(560); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self); form = QFormLayout()
        self.username = QLineEdit(user.username if user else "")
        self.username.setEnabled(user is None)
        self.display_name = QLineEdit(user.display_name if user else "")
        self.profile = QComboBox(); self.profile.addItems(application.list_profiles())
        if user: self.profile.setCurrentText(user.profile)
        self.active = QCheckBox("Usuário ativo"); self.active.setChecked(user.active if user else True)
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Vazia mantém a atual" if user else "Mínimo 6 caracteres ou vazia")
        form.addRow("Usuário*", self.username); form.addRow("Nome exibido*", self.display_name)
        form.addRow("Perfil*", self.profile); form.addRow("", self.active)
        form.addRow("Nova senha" if user else "Senha", self.password); root.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("Cancelar  [Esc]"); self.save = QPushButton("Salvar  [Enter]")
        self.save.setObjectName("primary"); cancel.clicked.connect(self.reject)
        self.save.clicked.connect(self._save); buttons.addWidget(cancel); buttons.addWidget(self.save)
        root.addLayout(buttons)
        self._fields = (self.username, self.display_name, self.profile, self.active, self.password, self.save)
        for field in self._fields: field.installEventFilter(self)
        escape = QShortcut(QKeySequence("Esc"), self); escape.setAutoRepeat(False)
        escape.activated.connect(self.reject)
        (self.display_name if user else self.username).setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.isAutoRepeat(): event.accept(); return True
            fields = tuple(field for field in self._fields if field.isEnabled() and not field.isHidden())
            index = fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                fields[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.save: self._save()
            else: fields[min(index + 1, len(fields) - 1)].setFocus(Qt.FocusReason.TabFocusReason)
            event.accept(); return True
        return super().eventFilter(watched, event)

    def _draft(self) -> UserDraft:
        return UserDraft(
            self.user.username if self.user else self.username.text(),
            self.display_name.text(), self.profile.currentText(),
            self.active.isChecked(), self.password.text(),
        )

    def _save(self) -> None:
        try:
            draft = self._draft()
            self.saved = self.application.update(self.user.username, draft) if self.user else self.application.create(draft)
        except Exception as error:
            QMessageBox.warning(self, "Usuários", str(error)); return
        self.accept()


class UsersDialog(QDialog):
    def __init__(self, application, parent=None) -> None:
        super().__init__(parent); self.application = application
        self.setWindowTitle("Usuários e acessos"); self.resize(860, 620); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("USUÁRIOS E ACESSOS")
        title.setStyleSheet("font-size:24px;font-weight:900;color:#58a6ff")
        root.addWidget(title)
        guidance = QLabel("Crie usuários individuais. Perfis e permissões permanecem sob o serviço de segurança.")
        guidance.setWordWrap(True); root.addWidget(guidance)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Usuário", "Nome", "Perfil", "Ativo"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_user); self.table.installEventFilter(self)
        root.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        new = QPushButton("Novo usuário  [F3]"); edit = QPushButton("Editar  [F4]")
        toggle = QPushButton("Ativar / Desativar"); close = QPushButton("Fechar  [Esc]")
        new.clicked.connect(self.new_user); edit.clicked.connect(self.edit_user)
        toggle.clicked.connect(self.toggle_active); close.clicked.connect(self.reject)
        for button in (new, edit, toggle): buttons.addWidget(button)
        buttons.addStretch(); buttons.addWidget(close); root.addLayout(buttons)
        self._shortcuts = []
        for key, callback in (("F3", self.new_user), ("F4", self.edit_user), ("F5", self.reload), ("Esc", self.reject)):
            shortcut = QShortcut(QKeySequence(key), self); shortcut.setAutoRepeat(False)
            shortcut.activated.connect(callback); self._shortcuts.append(shortcut)
        self.reload()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.table and event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.isAutoRepeat(): event.accept(); return True
            if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier: self.edit_user()
            event.accept(); return True
        return super().eventFilter(watched, event)

    def reload(self) -> None:
        try: users = self.application.list_users()
        except Exception as error:
            QMessageBox.warning(self, "Usuários", str(error)); return
        selected = self.selected_username(); self.table.setRowCount(0); selected_row = None
        for user in users:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (user.username, user.display_name, user.profile, "SIM" if user.active else "NÃO")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0: item.setData(Qt.ItemDataRole.UserRole, user.username)
                self.table.setItem(row, column, item)
            if user.username == selected: selected_row = row
        if self.table.rowCount(): self.table.selectRow(selected_row if selected_row is not None else 0)

    def selected_username(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None: return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def new_user(self) -> None:
        if UserEditorDialog(self.application, parent=self).exec() == QDialog.DialogCode.Accepted: self.reload()

    def edit_user(self) -> None:
        username = self.selected_username()
        if not username: return
        try: user = self.application.get_user(username)
        except Exception as error:
            QMessageBox.warning(self, "Usuários", str(error)); return
        if UserEditorDialog(self.application, user, self).exec() == QDialog.DialogCode.Accepted: self.reload()

    def toggle_active(self) -> None:
        username = self.selected_username()
        if not username: return
        answer = QMessageBox.question(
            self, "Alterar acesso", f"Alterar o estado de acesso de {username}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes: return
        try: self.application.toggle_active(username)
        except Exception as error:
            QMessageBox.warning(self, "Usuários", str(error)); return
        self.reload()
