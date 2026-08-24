import os
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from ui_qt.administration.login_dialog import ApplicationLoginDialog
from ui_qt.administration.module_hub import AdministrativeModule
from ui_qt.administration.dashboard_dialog import DashboardDialog
from ui_qt.shell import LEGACY_NAVIGATION, NabiCodeShellWindow
from ui_qt import app as qt_app
from core.startup_window_coordinator import SPLASH_PAUSE_ENV


@pytest.fixture(scope="module", autouse=True)
def qt_application():
    return QApplication.instance() or QApplication([])


class Security:
    def __init__(self):
        self.session = SimpleNamespace(user=SimpleNamespace(display_name="Operador"))
        self.touches = 0

    def is_expired(self): return False
    def require(self, _module, _action): return True
    def touch(self): self.touches += 1


def dashboard_module():
    return AdministrativeModule(
        "Início", "Resumo", "F1", "dashboard", "view", lambda p: QDialog(p),
        "dashboard", lambda p: QWidget(p),
    )


def summary_module(loader):
    module = dashboard_module()
    return AdministrativeModule(
        module.label, module.description, module.shortcut,
        module.permission_module, module.permission_action, module.factory,
        module.module_id, module.embedded_factory, loader,
    )


def test_manifest_preserves_exact_legacy_order_shortcuts_and_colors():
    assert [item.module_id for item in LEGACY_NAVIGATION] == [
        "dashboard", "vendas", "clientes", "produtos", "financeiro", "caixa",
        "fiscal", "relatorios", "configs",
    ]
    assert [item.shortcut for item in LEGACY_NAVIGATION[:4]] == ["F1", "F2", "F3", "F4"]
    assert LEGACY_NAVIGATION[-1].shortcut == "F5"
    assert [item.color for item in LEGACY_NAVIGATION] == [
        "#1f6feb", "#2ea043", "#8957e5", "#bf8700", "#0f766e",
        "#a16207", "#7c3aed", "#0369a1", "#da3633",
    ]


def test_shell_starts_on_dashboard_without_creating_pdv(qt_application):
    pdv_factory = Mock()
    shell = NabiCodeShellWindow(Security(), (dashboard_module(),), pdv_factory)
    try:
        assert shell._active_module == "dashboard"
        assert shell.pages.count() == 1
        assert list(shell.navigation_buttons) == [item.module_id for item in LEGACY_NAVIGATION]
        assert shell.navigation_buttons["fiscal"].isEnabled() is False
        pdv_factory.assert_not_called()
    finally:
        shell.close()


def test_f2_opens_one_independent_pdv_and_close_returns_to_start(qt_application):
    pdv = QMainWindow()
    factory = Mock(return_value=pdv)
    shell = NabiCodeShellWindow(Security(), (dashboard_module(),), factory)
    try:
        assert shell.open_pdv() is True
        assert shell._active_module == "vendas"
        assert shell.open_pdv() is False
        factory.assert_called_once_with()
        pdv.close()
        qt_application.processEvents()
        assert shell._pdv_window is None
        assert shell._active_module == "dashboard"
    finally:
        shell.close()


def test_enter_auto_repeat_on_vendas_is_consumed_without_opening(qt_application):
    factory = Mock(return_value=QMainWindow())
    shell = NabiCodeShellWindow(Security(), (dashboard_module(),), factory)
    try:
        button = shell.navigation_buttons["vendas"]
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier,
            "", True, 2,
        )
        assert shell.eventFilter(button, event) is True
        factory.assert_not_called()
    finally:
        shell.close()


def test_extra_module_goes_to_sidebar_without_reordering_legacy(qt_application):
    extra = AdministrativeModule(
        "Usuários", "Administração", "Ctrl+U", "technical", "users",
        lambda p: QDialog(p), "usuarios",
    )
    shell = NabiCodeShellWindow(
        Security(), (dashboard_module(), extra), lambda: QMainWindow()
    )
    try:
        assert list(shell.navigation_buttons) == [item.module_id for item in LEGACY_NAVIGATION]
        assert list(shell.favorite_buttons) == ["usuarios"]
    finally:
        shell.close()


def test_primary_module_is_embedded_and_reused_in_shell(qt_application):
    created = []
    def factory(parent):
        dialog = QDialog(parent); created.append(dialog); return dialog
    customers = AdministrativeModule(
        "Clientes", "Cadastro", "F3", "clientes", "view", factory, "clientes"
    )
    shell = NabiCodeShellWindow(
        Security(), (dashboard_module(), customers), lambda: QMainWindow()
    )
    try:
        assert shell.show_module("clientes") is True
        assert shell.pages.currentWidget() is created[0]
        assert created[0].isWindow() is False
        assert shell.show_module("clientes") is True
        assert len(created) == 1
        assert "border:3px solid #ffffff" in shell.navigation_buttons["clientes"].styleSheet()
        created[0].reject(); qt_application.processEvents()
        assert shell._active_module == "dashboard"
    finally:
        shell.close()


def test_login_is_large_and_preserves_one_enter_per_transition(qt_application):
    security = Mock(); security.authenticate.return_value = object()
    dialog = ApplicationLoginDialog(security)
    try:
        dialog.show(); qt_application.processEvents()
        assert dialog.minimumWidth() >= 680
        assert dialog.minimumHeight() >= 440
        dialog.username.setText("operador"); dialog.password.setText("segredo")
        dialog.username.setFocus()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        assert dialog.eventFilter(dialog.username, event) is True
        qt_application.processEvents()
        security.authenticate.assert_not_called()
        assert dialog.password.hasFocus()
    finally:
        dialog.close()


def test_qt_splash_wrapper_reuses_canonical_process_contract():
    process = Mock()
    paths = tuple(Mock() for _ in range(4))
    with patch("main._start_splash", return_value=(process, *paths)), patch(
        "main._stop_splash"
    ) as stop, patch("main._ensure_process_stopped", return_value=True) as ensure, patch(
        "main._cleanup_splash_files"
    ) as cleanup:
        from core.qt_startup_splash import QtStartupSplash
        splash = QtStartupSplash(); splash.close(); splash.close()
    stop.assert_called_once_with(paths[0])
    ensure.assert_called_once_with(process, timeout=15.0)
    cleanup.assert_called_once_with(*paths)
    assert SPLASH_PAUSE_ENV not in os.environ


def test_splash_creation_failure_is_recoverable_and_close_is_idempotent():
    os.environ[SPLASH_PAUSE_ENV] = "arquivo-antigo"
    with patch("main._start_splash", side_effect=OSError("helper indisponível")):
        from core.qt_startup_splash import QtStartupSplash
        splash = QtStartupSplash(); splash.close(); splash.close()
    assert splash.closed is True
    assert SPLASH_PAUSE_ENV not in os.environ


def test_application_shell_does_not_construct_pdv_during_startup(qt_application):
    with patch.object(qt_app, "PDVWindow", autospec=True) as pdv:
        _application, shell = qt_app.create_shell_application(
            object(), Security(), (dashboard_module(),), argv=[]
        )
        try:
            pdv.assert_not_called()
        finally:
            shell.close()


def test_attaching_nabi_panel_does_not_open_sales(qt_application):
    panel = QWidget()
    with patch.object(qt_app, "PDVWindow", autospec=True) as pdv:
        _application, shell = qt_app.create_shell_application(
            object(), Security(), (dashboard_module(),), argv=[],
            assistant_panel_factory=lambda _parent: panel,
        )
        try:
            assert shell.nabi_assistant_dock.widget() is panel
            pdv.assert_not_called()
        finally:
            shell.close()


def test_expired_session_reauthenticates_once_and_retries_action(qt_application):
    security = Security(); security.expired = False
    security.is_expired = lambda: security.expired
    calls = []
    def reauthenticate(_parent):
        calls.append(1); security.session = object(); security.expired = False; return True
    customers = AdministrativeModule(
        "Clientes", "Cadastro", "F3", "clientes", "view",
        lambda p: QDialog(p), "clientes",
    )
    shell = NabiCodeShellWindow(
        security, (dashboard_module(), customers), lambda: QMainWindow(),
        reauthenticate=reauthenticate,
    )
    try:
        security.session = None; security.expired = True
        assert shell.show_module("clientes") is True
        assert len(calls) == 1
        assert shell._active_module == "clientes"
    finally: shell.close()


def test_cancelled_or_ineffective_reauthentication_fails_closed_without_loop(qt_application):
    security = Security(); security.expired = False
    security.is_expired = lambda: security.expired
    customers = AdministrativeModule(
        "Clientes", "Cadastro", "F3", "clientes", "view",
        lambda p: QDialog(p), "clientes",
    )
    for result in (False, True):
        security.session = object(); security.expired = False
        callback = Mock(return_value=result)
        shell = NabiCodeShellWindow(
            security, (dashboard_module(), customers), lambda: QMainWindow(),
            reauthenticate=callback,
        )
        try:
            security.session = None; security.expired = True
            with patch("ui_qt.shell.main_window.QMessageBox.warning"):
                assert shell.show_module("clientes") is False
            callback.assert_called_once_with(shell)
        finally: shell.close()


def test_summary_worker_updates_values_and_reports_error(qt_application):
    values = SimpleNamespace(
        total_records=12, current_count=7, owing_count=3,
        owing_value=Decimal("45.50"), alert_count=2,
        alert_value=Decimal("80.00"),
    )
    shell = NabiCodeShellWindow(
        Security(), (summary_module(lambda: values),), lambda: QMainWindow()
    )
    try:
        deadline = time.monotonic() + 2
        while "12" not in shell.summary_labels["total"].text() and time.monotonic() < deadline:
            qt_application.processEvents(); time.sleep(0.01)
        assert shell.summary_labels["total"].text() == "Total de Fichas: 12"
        assert "R$ 45.50" in shell.summary_labels["owing"].text()
        shell._modules["dashboard"] = summary_module(lambda: (_ for _ in ()).throw(RuntimeError("falha")))
        shell.refresh_summary()
        deadline = time.monotonic() + 2
        while "Indisponível" not in shell.summary_labels["total"].text() and time.monotonic() < deadline:
            qt_application.processEvents(); time.sleep(0.01)
        assert shell.summary_labels["total"].text() == "Fichas: Indisponível"
    finally: shell.close()


def test_stale_summary_is_discarded(qt_application):
    old = SimpleNamespace(total_records=1,current_count=1,owing_count=0,owing_value=Decimal(0),alert_count=0,alert_value=Decimal(0))
    new = SimpleNamespace(total_records=9,current_count=9,owing_count=0,owing_value=Decimal(0),alert_count=0,alert_value=Decimal(0))
    shell = NabiCodeShellWindow(
        Security(), (dashboard_module(),), lambda: QMainWindow()
    )
    try:
        shell._summary_generation = 2
        shell._summary_loaded(1, old, None)
        assert shell.summary_labels["total"].text() != "Total de Fichas: 1"
        shell._summary_loaded(2, new, None)
        assert shell.summary_labels["total"].text() == "Total de Fichas: 9"
    finally: shell.close()


def test_shell_closes_embedded_module_and_dashboard_workers(qt_application):
    class SlowDashboard:
        def load(self, **_kwargs):
            time.sleep(0.05)
            raise RuntimeError("consulta encerrada")
    dashboard = AdministrativeModule(
        "Início", "Resumo", "F1", "dashboard", "view", lambda p: QDialog(p),
        "dashboard", lambda p: DashboardDialog(
            SlowDashboard(), p, embedded=True, worker_pool=p.window().worker_pool
        ), lambda: SimpleNamespace(
            total_records=0,current_count=0,owing_count=0,owing_value=Decimal(0),
            alert_count=0,alert_value=Decimal(0),
        ),
    )
    page = QDialog()
    customers = AdministrativeModule(
        "Clientes", "Cadastro", "F3", "clientes", "view",
        lambda parent: (page.setParent(parent) or page), "clientes",
    )
    with patch("ui_qt.administration.dashboard_dialog.QMessageBox.warning"):
        shell = NabiCodeShellWindow(Security(), (dashboard, customers), lambda: QMainWindow())
        shell.show(); qt_application.processEvents()
        assert shell.show_module("clientes") is True
        shell.close(); qt_application.processEvents()
    assert shell.worker_pool.activeThreadCount() == 0
    assert page.isVisible() is False
