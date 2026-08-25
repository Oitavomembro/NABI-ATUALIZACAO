import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from ui_qt.administration.fiscal_readiness_dialog import FiscalReadinessDialog


def setup_module():
    global APP
    APP = QApplication.instance() or QApplication([])


def snapshot():
    return SimpleNamespace(
        state="BLOQUEADO", environment="HOMOLOGACAO", enabled=False,
        issuer_document="Não configurado", issuer_state="BA",
        tax_regime="SIMPLES_NACIONAL", certificate_configured=False,
        certificate_name="Não configurado", models=(), notices=(),
    )


def test_clique_configurar_abre_dialogo_exatamente_uma_vez():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application)
    with patch("ui_qt.administration.fiscal_readiness_dialog.FiscalConfigurationDialog") as factory:
        child = factory.return_value; child.exec.return_value = QDialog.DialogCode.Rejected
        QTest.mouseClick(dialog.configure_button, Qt.MouseButton.LeftButton)
        factory.assert_called_once_with(application, dialog)
        child.exec.assert_called_once_with()
    dialog.close()


def test_clique_atualizar_recarrega_e_fechar_encerra():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application)
    QTest.mouseClick(dialog.refresh_button, Qt.MouseButton.LeftButton)
    assert application.snapshot.call_count == 2
    QTest.mouseClick(dialog.close_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_enter_configura_uma_vez_e_auto_repeat_nao_abre():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application); dialog.configure = Mock(return_value=False)
    enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    assert dialog.eventFilter(dialog.configure_button, enter) is True
    dialog.configure.assert_called_once_with()
    repeated = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier,
        "", True, 2,
    )
    assert dialog.eventFilter(dialog.configure_button, repeated) is True
    assert dialog.configure.call_count == 1
    dialog.close()


def test_shift_enter_apenas_move_foco_sem_executar():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application); dialog.configure = Mock()
    dialog.show(); dialog.activateWindow(); APP.processEvents()
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier,
    )
    assert dialog.eventFilter(dialog.refresh_button, event) is True
    APP.processEvents()
    assert dialog.focusWidget() is dialog.configure_button
    dialog.configure.assert_not_called(); dialog.close()
