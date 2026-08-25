from __future__ import annotations

import os
import ast
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from ui_qt.administration.backup_package_dialog import BackupPackageDialog


APP = QApplication.instance() or QApplication([])


class Application:
    def __init__(self):
        self.calls = []

    def create_backup_package(self, **values):
        self.calls.append(values)
        return SimpleNamespace(
            filename="backup_manual_protegido.nabibackup",
            encrypted=values["encrypted"],
            schema_version=21,
            sha256="a" * 64,
        )


class ImmediatePool:
    def start(self, worker): worker.run()


class HoldingPool:
    def __init__(self): self.workers = []
    def start(self, worker): self.workers.append(worker)


def _enter(*, repeat=False, shift=False):
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        "\r", repeat, 1,
    )


def test_criptografado_e_padrao_recomendado_e_senha_some_apos_iniciar(tmp_path):
    application = Application()
    dialog = BackupPackageDialog(
        application, initial_directory=str(tmp_path), worker_pool=ImmediatePool()
    )
    assert dialog.mode.currentText() == dialog.ENCRYPTED
    dialog.password.setText("senha efemera segura")
    dialog.confirm_password.setText("senha efemera segura")
    dialog._start()
    assert len(application.calls) == 1
    assert application.calls[0]["encrypted"] is True
    assert dialog.password.text() == dialog.confirm_password.text() == ""
    assert "BACKUP COMPROVADO" in dialog.result.toPlainText()
    assert "senha efemera segura" not in dialog.result.toPlainText()
    dialog.close()


def test_legado_exibe_alerta_inseguro_e_nao_solicita_senha(tmp_path):
    application = Application()
    dialog = BackupPackageDialog(application, initial_directory=str(tmp_path), worker_pool=ImmediatePool())
    dialog.show(); APP.processEvents()
    dialog.mode.setCurrentText(dialog.LEGACY)
    assert not dialog.password.isVisible()
    assert "sem criptografia" in dialog.warning.text()
    dialog._start()
    assert application.calls[0]["encrypted"] is False
    assert application.calls[0]["password"] == ""
    dialog.close()


def test_senhas_divergentes_nao_iniciam_worker(tmp_path):
    application = Application()
    dialog = BackupPackageDialog(application, initial_directory=str(tmp_path), worker_pool=ImmediatePool())
    dialog.password.setText("senha efemera segura")
    dialog.confirm_password.setText("senha diferente segura")
    dialog._start()
    assert application.calls == []
    assert "senhas iguais" in dialog.result.toPlainText()
    dialog.close()


def test_reentrada_e_bloqueada_e_cancelamento_limpa_campos(tmp_path):
    application = Application(); pool = HoldingPool()
    dialog = BackupPackageDialog(application, initial_directory=str(tmp_path), worker_pool=pool)
    dialog.password.setText("senha efemera segura")
    dialog.confirm_password.setText("senha efemera segura")
    dialog._start(); dialog._start()
    assert len(pool.workers) == 1
    assert dialog.password.text() == dialog.confirm_password.text() == ""
    dialog.reject()
    assert dialog.isVisible() is False
    assert dialog._busy is True
    pool.workers[0].run()
    assert len(application.calls) == 1
    dialog.close()


def test_auto_repeat_shift_enter_e_escape_nao_geram_backup(tmp_path):
    application = Application()
    dialog = BackupPackageDialog(application, initial_directory=str(tmp_path), worker_pool=ImmediatePool())
    assert dialog.eventFilter(dialog.generate, _enter(repeat=True)) is True
    assert dialog.eventFilter(dialog.generate, _enter(shift=True)) is True
    assert application.calls == []
    dialog.password.setText("segredo temporario")
    escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert dialog.eventFilter(dialog.password, escape) is True
    assert dialog.password.text() == ""


def test_enter_avanca_um_campo_por_vez_antes_de_gerar(tmp_path):
    application = Application()
    dialog = BackupPackageDialog(application, initial_directory=str(tmp_path), worker_pool=ImmediatePool())
    dialog.show(); APP.processEvents()
    assert dialog.eventFilter(dialog.destination, _enter()) is True
    assert dialog.mode.hasFocus()
    assert dialog.eventFilter(dialog.mode, _enter()) is True
    assert dialog.password.hasFocus()
    assert dialog.eventFilter(dialog.password, _enter()) is True
    assert dialog.confirm_password.hasFocus()
    assert application.calls == []
    dialog.close()


def test_falha_nao_exibe_caminho_senha_ou_excecao(tmp_path):
    class BrokenApplication:
        def create_backup_package(self, **_values):
            raise RuntimeError(f"segredo em {tmp_path}")

    dialog = BackupPackageDialog(
        BrokenApplication(), initial_directory=str(tmp_path), worker_pool=ImmediatePool()
    )
    dialog.password.setText("senha efemera segura")
    dialog.confirm_password.setText("senha efemera segura")
    dialog._start()
    text = dialog.result.toPlainText()
    assert str(tmp_path) not in text
    assert "senha efemera segura" not in text
    assert "RuntimeError" not in text
    dialog.close()


def test_dialogo_nao_importa_banco_fiscal_ia_ou_licenciamento():
    source = Path(__file__).parents[1].joinpath(
        "ui_qt/administration/backup_package_dialog.py"
    ).read_text(encoding="utf-8")
    modules = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(str(node.module or "").lower())
    forbidden = ("sqlite3", "database", "fiscal", "assistant_nabi", "licensing")
    assert not any(any(item in module for item in forbidden) for module in modules)
