from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from services.backup_service import BackupDestinationResult, BackupResult
from ui_qt.backup_startup import DailyBackupController


APP = QApplication.instance() or QApplication([])


class DeferredPool:
    def __init__(self): self.runnables = []
    def start(self, runnable): self.runnables.append(runnable)


class Window(QWidget):
    def __init__(self): super().__init__(); self.messages = []
    def _notify_known_state(self, text): self.messages.append(text)


def result(*, status="success"):
    if status == "disabled": return BackupResult((), (), skipped=True)
    local = BackupDestinationResult("local", True, database_backup="local.db")
    if status == "success":
        cloud = BackupDestinationResult("cloud", True, database_backup="cloud.db")
        return BackupResult(("local.db", "cloud.db"), (), destinations=(local, cloud))
    cloud = BackupDestinationResult("cloud", False, error="offline")
    return BackupResult(("local.db",), ("cloud: offline",), destinations=(local, cloud))


def test_startup_nao_bloqueia_e_impede_execucao_concorrente():
    pool = DeferredPool(); window = Window()
    service = SimpleNamespace(run_daily=lambda: result())
    controller = DailyBackupController(service, window, pool=pool)
    assert controller.start() is True
    assert controller.start() is False
    assert len(pool.runnables) == 1
    assert window.messages == []
    pool.runnables[0].run(); APP.processEvents()
    assert window.messages == ["Backup diário concluído (2/2 destinos)"]


def test_resultado_parcial_e_visivel_e_nunca_alega_duas_copias():
    window = Window(); controller = DailyBackupController(None, window, pool=DeferredPool())
    with patch("ui_qt.backup_startup.QMessageBox.warning") as warning:
        controller._completed(result(status="partial"))
    assert window.messages[-1] == "Backup diário parcial (1/2 destinos)"
    text = warning.call_args.args[2]
    assert "cloud: offline" in text
    assert "dados pessoais" in text
    assert "concluído (2/2" not in text


def test_desativado_informa_estado_real_sem_abrir_aviso():
    window = Window(); controller = DailyBackupController(None, window, pool=DeferredPool())
    with patch("ui_qt.backup_startup.QMessageBox.warning") as warning:
        controller._completed(result(status="disabled"))
    assert window.messages[-1] == "Backup diário desativado"
    warning.assert_not_called()


def test_excecao_nao_marca_sucesso_e_exibe_falha_honesta():
    window = Window(); controller = DailyBackupController(None, window, pool=DeferredPool())
    with patch("ui_qt.backup_startup.QMessageBox.warning") as warning:
        controller._failed(RuntimeError("banco indisponível"))
    assert "falhou" in window.messages[-1]
    assert "banco indisponível" in warning.call_args.args[2]


def test_startup_constroi_backup_somente_depois_de_licenca_banco_e_login():
    source = __import__("pathlib").Path("main_qt.py").read_text(encoding="utf-8")
    license_gate = source.index("license_gate = evaluate_runtime_gate")
    database = source.index("database = DatabaseManager")
    login = source.index("if ApplicationLoginDialog(module_security).exec()")
    backup = source.index("daily_backup = BackupService")
    shell = source.index("return run_shell(")
    assert license_gate < database < login < backup < shell
