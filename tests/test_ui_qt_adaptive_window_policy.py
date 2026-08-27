import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QMessageBox, QPushButton

from ui_qt.adaptive_window_policy import install_adaptive_window_policy


APP = QApplication.instance() or QApplication([])


def test_dialogo_operacional_abre_amplo_e_dentro_da_area_util():
    install_adaptive_window_policy(APP)
    dialog = QDialog(); dialog.resize(320, 240); dialog.show()
    APP.processEvents()
    assert dialog.width() >= min(720, dialog.screen().availableGeometry().width())
    assert dialog.height() >= min(520, dialog.screen().availableGeometry().height())
    assert dialog.screen().availableGeometry().contains(dialog.frameGeometry())
    dialog.close()


def test_dialogo_com_botao_chamado_move_abre_amplo_sem_erro():
    install_adaptive_window_policy(APP)
    dialog = QDialog(); dialog.move = QPushButton("Movimentar", dialog)
    dialog.resize(320, 240); dialog.show(); APP.processEvents()
    assert dialog.width() >= min(720, dialog.screen().availableGeometry().width())
    assert dialog.screen().availableGeometry().contains(dialog.frameGeometry())
    dialog.close()


def test_janela_maximizada_nao_e_reduzida_depois_do_show():
    install_adaptive_window_policy(APP)
    dialog = QDialog(); dialog.resize(320, 240); dialog.showMaximized()
    APP.processEvents()
    assert dialog.isMaximized()
    dialog.close()


def test_aviso_curto_permanece_compacto():
    install_adaptive_window_policy(APP)
    message = QMessageBox(); message.resize(360, 180); message.show()
    APP.processEvents()
    assert message.width() < 720
    message.close()


def test_roda_do_mouse_nao_altera_seletor_fechado():
    policy = install_adaptive_window_policy(APP)
    combo = QComboBox(); combo.addItems(("Primeiro", "Segundo", "Terceiro"))
    combo.setCurrentIndex(1)
    event = Mock()
    event.type.return_value = QEvent.Type.Wheel
    assert policy.eventFilter(combo, event) is True
    event.ignore.assert_called_once_with()
    assert combo.currentIndex() == 1
