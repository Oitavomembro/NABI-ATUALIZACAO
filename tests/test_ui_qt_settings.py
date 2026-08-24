from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from services.ui_preferences import UIPreferencesService
from ui_qt.administration.settings_dialog import SettingsDialog


APP = QApplication.instance() or QApplication([])


class Application:
    def __init__(self, *, editable=True):
        self.editable = editable; self.backups = 0; self.diagnostics = 0; self.saved = []
    def load(self):
        return SimpleNamespace(
            username="maria",
            preferences=UIPreferencesService.normalize({}),
            backup_directories=("C:\\Teste\\backups",),
            daily_backup_enabled=True,
        )
    def can(self, action): return self.editable
    def save_preferences(self, values): self.saved.append(dict(values)); return self.load()
    def configure_backup(self, **values): self.saved.append(values); return self.load()
    def create_backup(self):
        self.backups += 1; return SimpleNamespace(created=("C:\\Teste\\backup.db",))
    def run_diagnostics(self):
        self.diagnostics += 1; return {"aprovado": True}, "SISTEMA APROVADO"


def _enter(*, repeat=False):
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier, "\r", repeat, 1,
    )


def test_carrega_preferencias_e_respeita_permissao_somente_leitura():
    dialog = SettingsDialog(Application(editable=False))
    assert dialog.mode.currentText() == "Intermediário"
    assert not dialog.save_interface.isEnabled()
    assert not dialog.backup_now.isEnabled()
    dialog.close()


def test_auto_repeat_e_consumido_sem_disparar_backup():
    application = Application(); dialog = SettingsDialog(application)
    assert dialog.eventFilter(dialog.backup_now, _enter(repeat=True)) is True
    assert application.backups == 0
    dialog.close()


def test_diagnostico_exibe_resultado_sem_persistencia_na_gui():
    application = Application(); dialog = SettingsDialog(application)
    dialog._run_diagnostics()
    assert application.diagnostics == 1
    assert "SISTEMA APROVADO" in dialog.diagnostic_text.toPlainText()
    dialog.close()


def test_gui_nao_importa_banco_repositorios_fiscal_ou_legacy():
    source = Path(__file__).parents[1].joinpath(
        "ui_qt/administration/settings_dialog.py"
    ).read_text(encoding="utf-8")
    modules = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import): modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom): modules.append(str(node.module or "").lower())
    for forbidden in ("sqlite3", "database", "repositories", "fiscal", "sefaz", "nabicode_legacy"):
        assert not any(forbidden in module for module in modules)
