from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ui_qt.administration.data_maintenance_dialog import DataMaintenanceDialog


@pytest.fixture(scope="module")
def qt_application():
    application = QApplication.instance() or QApplication([])
    yield application


def test_dialogo_explica_limite_e_oferece_as_tres_acoes(qt_application):
    dialog = DataMaintenanceDialog(Mock())
    text = " ".join(label.text() for label in dialog.findChildren(type(dialog.close_button)))
    assert dialog.preview_migration.text() == "Analisar sem importar"
    assert dialog.verify_button.text() == "Verificar somente em TEMP"
    assert dialog.prepare_button.text() == "Preparar restauração e pré-backup"
    assert dialog.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint


def test_preview_habilita_importacao_mas_nao_importa(qt_application):
    app = Mock()
    app.preview_migration.return_value = SimpleNamespace(
        package_sha256="a" * 64, ready=True, source_system="Teste", package="x",
        counts={"customers": 1}, warnings=(), errors=(),
    )
    app.migration_confirmation.return_value = "IMPORTAR AAAAAAAAAAAA"
    dialog = DataMaintenanceDialog(app); dialog.migration_path.setText("x.nabimig")
    dialog._preview_migration()
    assert dialog.import_button.isEnabled()
    app.execute_migration.assert_not_called()


def test_verificacao_em_temp_nao_prepara_automaticamente(qt_application):
    app = Mock()
    app.verify_backup.return_value = SimpleNamespace(
        sha256="b" * 64, backup_format="NABICODE_ENCRYPTED_V1", schema_version=32,
    )
    app.restore_confirmation.return_value = "PREPARAR BBBBBBBBBBBB"
    dialog = DataMaintenanceDialog(app); dialog.backup_path.setText("x.nabibackup")
    dialog._verify_backup()
    assert dialog.prepare_button.isEnabled()
    app.prepare_restore.assert_not_called()
    assert "não foi alterado" in dialog.output.toPlainText()


def test_escape_e_auto_repeat_nao_executam_operacao(qt_application):
    app = Mock(); dialog = DataMaintenanceDialog(app); dialog.show()
    repeated = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier, "\r", True, 2,
    )
    QApplication.sendEvent(dialog.choose_migration, repeated)
    app.preview_migration.assert_not_called(); app.execute_migration.assert_not_called()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
