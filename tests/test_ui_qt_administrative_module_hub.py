from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog

from ui_qt.administration.module_hub import AdministrativeModule, AdministrativeModuleHub


def _module(factory=None):
    return AdministrativeModule(
        "Clientes", "Cadastro, busca e fichas", "F3", "clientes", "view",
        factory or (lambda parent: QDialog(parent)),
    )


def _security(*, allowed=True, expired=False):
    security = Mock()
    security.session = SimpleNamespace(
        user=SimpleNamespace(display_name="Administrador", profile="ADMIN")
    )
    security.is_expired.return_value = expired
    security.require.return_value = allowed
    return security


def _enter(*, shift=False, repeat=False):
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        "", repeat, 1,
    )


def setup_module():
    global APP
    APP = QApplication.instance() or QApplication([])


def test_abertura_valida_permissao_toca_sessao_e_abre_uma_vez():
    security = _security()
    dialog = Mock(spec=QDialog)
    hub = AdministrativeModuleHub(security, (_module(lambda _parent: dialog),))
    assert hub.open_module(hub.modules[0]) is True
    security.require.assert_called_once_with("clientes", "view")
    security.touch.assert_called_once_with()
    dialog.exec.assert_called_once_with()
    hub.close()


def test_sessao_expirada_e_permissao_negada_falham_fechado():
    for security in (_security(expired=True), _security(allowed=False)):
        factory = Mock()
        hub = AdministrativeModuleHub(security, (_module(factory),))
        with patch("ui_qt.administration.module_hub.QMessageBox.warning"):
            assert hub.open_module(hub.modules[0]) is False
        factory.assert_not_called()
        hub.close()


def test_enter_auto_repeat_e_consumido_sem_abrir():
    factory = Mock()
    hub = AdministrativeModuleHub(_security(), (_module(factory),))
    assert hub.eventFilter(hub.buttons[0], _enter(repeat=True)) is True
    factory.assert_not_called()
    hub.close()


def test_um_enter_abre_exatamente_um_modulo():
    dialog = Mock(spec=QDialog)
    factory = Mock(return_value=dialog)
    hub = AdministrativeModuleHub(_security(), (_module(factory),))
    assert hub.eventFilter(hub.buttons[0], _enter()) is True
    factory.assert_called_once_with(hub)
    dialog.exec.assert_called_once_with()
    hub.close()


def test_shift_enter_volta_sem_abrir_modulo():
    first = _module(Mock())
    second_factory = Mock()
    second = AdministrativeModule(
        "Caixa", "Abertura e fechamento", "F6", "financeiro", "view",
        second_factory,
    )
    hub = AdministrativeModuleHub(_security(), (first, second))
    hub.show()
    hub.buttons[1].setFocus()
    APP.processEvents()
    assert hub.eventFilter(hub.buttons[1], _enter(shift=True)) is True
    APP.processEvents()
    assert hub.buttons[0].hasFocus()
    second_factory.assert_not_called()
    hub.close()


def test_factory_deve_retornar_dialogo_qt():
    hub = AdministrativeModuleHub(_security(), (_module(lambda _parent: object()),))
    with patch("ui_qt.administration.module_hub.QMessageBox.warning") as warning:
        assert hub.open_module(hub.modules[0]) is False
    assert "janela Qt" in str(warning.call_args.args[2])
    hub.close()
