import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

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


def test_aviso_curto_permanece_compacto():
    install_adaptive_window_policy(APP)
    message = QMessageBox(); message.resize(360, 180); message.show()
    APP.processEvents()
    assert message.width() < 720
    message.close()
