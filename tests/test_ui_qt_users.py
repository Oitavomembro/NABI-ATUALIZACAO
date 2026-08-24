from __future__ import annotations

import ast
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from services.security_service import SecurityUser
from ui_qt.administration.users_dialog import UserEditorDialog, UsersDialog


APP = QApplication.instance() or QApplication([])


class Application:
    def __init__(self):
        self.users = [SecurityUser("admin", "Administrador", "ADMIN", True)]
        self.created = []; self.updated = []; self.toggled = []
    def list_profiles(self): return ("ADMIN", "GERENTE", "OPERADOR")
    def list_users(self): return tuple(self.users)
    def get_user(self, username): return next(user for user in self.users if user.username == username)
    def create(self, draft): self.created.append(draft); return self.users[0]
    def update(self, username, draft): self.updated.append((username, draft)); return self.users[0]
    def toggle_active(self, username): self.toggled.append(username); return self.users[0]


def _enter(*, shift=False, repeat=False):
    modifiers = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, modifiers, "\r", repeat, 1)


def test_editor_enter_avanca_e_salva_exatamente_uma_vez():
    application = Application(); dialog = UserEditorDialog(application)
    dialog.show(); APP.processEvents(); dialog.username.setText("maria"); dialog.display_name.setText("Maria")
    assert dialog.eventFilter(dialog.username, _enter()); APP.processEvents()
    assert dialog.display_name.hasFocus()
    assert dialog.eventFilter(dialog.save, _enter())
    assert len(application.created) == 1
    dialog.close()


def test_editor_shift_enter_volta_e_auto_repeat_nao_salva():
    application = Application(); dialog = UserEditorDialog(application)
    dialog.show(); dialog.profile.setFocus(); APP.processEvents()
    assert dialog.eventFilter(dialog.profile, _enter(shift=True)); APP.processEvents()
    assert dialog.display_name.hasFocus()
    assert dialog.eventFilter(dialog.save, _enter(repeat=True))
    assert application.created == []
    dialog.close()


def test_lista_preserva_username_real_no_item():
    dialog = UsersDialog(Application())
    assert dialog.table.rowCount() == 1
    assert dialog.selected_username() == "admin"
    dialog.close()


def test_gui_nao_importa_banco_repositorio_fiscal_ou_legacy():
    from pathlib import Path
    source = Path(__file__).parents[1].joinpath("ui_qt/administration/users_dialog.py").read_text(encoding="utf-8")
    modules = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import): modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom): modules.append(str(node.module or "").lower())
    for forbidden in ("sqlite3", "database", "repositories", "fiscal", "sefaz", "nabicode_legacy"):
        assert not any(forbidden in module for module in modules)
