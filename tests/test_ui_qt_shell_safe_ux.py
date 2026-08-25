import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from ui_qt.administration.module_hub import AdministrativeModule
from ui_qt.shell.main_window import NabiCodeShellWindow


APP = QApplication.instance() or QApplication([])


class Security:
    def __init__(self, allowed=None):
        self.allowed = set(allowed or {("dashboard", "view")})
        self.session = SimpleNamespace(
            user=SimpleNamespace(username="maria", display_name="Maria")
        )
        self.expired = False

    def is_expired(self): return self.expired
    def require(self, module, action): return (module, action) in self.allowed
    def touch(self): return None


def module(module_id, label, permission=None):
    permission = permission or module_id
    return AdministrativeModule(
        label, f"Descrição de {label}", "", permission, "view",
        lambda parent: QDialog(parent), module_id,
        (lambda parent: QWidget(parent)) if module_id == "dashboard" else None,
    )


def settings(tmp_path):
    return QSettings(str(tmp_path / "ux.ini"), QSettings.Format.IniFormat)


def shell(tmp_path, security, modules):
    return NabiCodeShellWindow(
        security, modules, lambda: QMainWindow(), ux_settings=settings(tmp_path)
    )


def enter(*, repeat=False, shift=False):
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        "", repeat, 1,
    )


def test_busca_indexa_somente_modulos_visiveis_e_autorizados(tmp_path):
    security = Security({("dashboard", "view"), ("clientes", "view")})
    window = shell(tmp_path, security, (
        module("dashboard", "Início"), module("clientes", "Clientes"),
        module("auditoria", "Auditoria", "technical"),
    ))
    try:
        window._refresh_module_search("")
        window._refresh_module_search("clientes")
        assert window.module_results.count() == 1
        assert window.module_results.item(0).data(Qt.ItemDataRole.UserRole) == "clientes"
        window._refresh_module_search("auditoria")
        assert window.module_results.count() == 0
        assert "auditoria" not in window.auxiliary_buttons
    finally: window.close()


def test_enter_unico_abre_um_resultado_e_ambiguidade_exige_selecao(tmp_path):
    security = Security({("dashboard", "view"), ("clientes", "view"), ("produtos", "view")})
    window = shell(tmp_path, security, (
        module("dashboard", "Início"), module("clientes", "Clientes"),
        module("produtos", "Produtos"),
    ))
    try:
        window.show(); APP.processEvents()
        window.module_search.setText("clientes")
        with patch.object(window, "show_module", return_value=True) as opening:
            assert window.eventFilter(window.module_search, enter()) is True
            opening.assert_called_once_with("clientes")
        window.module_search.setText("o")
        assert window.module_results.count() > 1
        with patch.object(window, "show_module", return_value=True) as opening:
            assert window.eventFilter(window.module_search, enter()) is True
            opening.assert_not_called()
            assert window.module_results.hasFocus()
            assert window.eventFilter(window.module_results, enter()) is True
            opening.assert_called_once()
        window.module_search.setText("clientes")
        with patch.object(window, "show_module", return_value=True) as opening:
            assert window.eventFilter(window.module_search, enter(repeat=True)) is True
            opening.assert_not_called()
    finally: window.close()


def test_favorito_persiste_por_usuario_e_some_quando_permissao_expira(tmp_path):
    security = Security({("dashboard", "view"), ("clientes", "view")})
    preferences = settings(tmp_path)
    window = NabiCodeShellWindow(
        security, (module("dashboard", "Início"), module("clientes", "Clientes")),
        lambda: QMainWindow(), ux_settings=preferences,
    )
    try:
        window._active_module = "clientes"
        assert window._toggle_active_favorite() is True
        assert "clientes" in window.favorite_buttons
        stored = json.loads(preferences.value("users/maria/preferences"))
        assert stored["favorites"] == ["clientes"]
        security.allowed.remove(("clientes", "view"))
        window._refresh_favorites()
        assert "clientes" not in window.favorite_buttons
        stored = json.loads(preferences.value("users/maria/preferences"))
        assert stored["favorites"] == []
    finally: window.close()


def test_densidade_e_fonte_sao_normalizadas_e_aplicadas_sem_mudar_ordem(tmp_path):
    window = shell(tmp_path, Security(), (module("dashboard", "Início"),))
    try:
        original_order = tuple(window.navigation_buttons)
        window.apply_ui_preferences({"density": "Compacta", "font_size": 9})
        assert window.font().pointSize() == 10
        assert all(button.height() == 70 for button in window.navigation_buttons.values())
        window.apply_ui_preferences({"density": "Confortável", "font_size": 30})
        assert window.font().pointSize() == 22
        assert all(button.height() == 94 for button in window.navigation_buttons.values())
        assert tuple(window.navigation_buttons) == original_order
    finally: window.close()


def test_notificacao_so_muda_depois_de_abertura_confirmada(tmp_path):
    security = Security({("dashboard", "view"), ("clientes", "view")})
    failing = AdministrativeModule(
        "Clientes", "Falha", "", "clientes", "view",
        lambda _parent: (_ for _ in ()).throw(RuntimeError("falhou")), "clientes",
    )
    window = shell(tmp_path, security, (module("dashboard", "Início"), failing))
    try:
        before = window.status_notification.text()
        with patch("ui_qt.shell.main_window.QMessageBox.warning"):
            assert window.show_module("clientes") is False
        assert window.status_notification.text() == before
    finally: window.close()
