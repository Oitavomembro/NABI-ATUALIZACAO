import os
import time
from decimal import Decimal
from pathlib import Path
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
    assert LEGACY_NAVIGATION[-1].label == "Configurações"
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
        assert shell.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
        assert shell.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
        assert shell.windowFlags() & Qt.WindowType.WindowCloseButtonHint
        pdv_factory.assert_not_called()
    finally:
        shell.close()


def test_navigation_cards_are_large_descriptive_and_arranged_in_three_columns(qt_application):
    shell = NabiCodeShellWindow(Security(), (dashboard_module(),), Mock())
    try:
        vendas = shell.navigation_buttons["vendas"]
        fiscal = shell.navigation_buttons["fiscal"]
        assert vendas.sizeHint().height() >= 70
        assert "qlineargradient" in vendas.styleSheet()
        assert "border-bottom:6px" in vendas.styleSheet()
        assert "PDV, pagamentos e comprovantes" in vendas.text()
        assert "Documentos e comunicação fiscal" in fiscal.text()
        positions = {
            shell.navigation_buttons[item.module_id]: (index // 3, index % 3)
            for index, item in enumerate(LEGACY_NAVIGATION)
        }
        assert positions[shell.navigation_buttons["dashboard"]] == (0, 0)
        assert positions[shell.navigation_buttons["financeiro"]] == (1, 1)
        assert positions[shell.navigation_buttons["configs"]] == (2, 2)
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


def test_sidebar_exibe_extra_operacional_e_oculta_modulo_tecnico(qt_application):
    technical = AdministrativeModule(
        "Usuários", "Administração", "Ctrl+U", "technical", "users",
        lambda p: QDialog(p), "usuarios", restricted_menu=True,
    )
    extra = AdministrativeModule(
        "Central do Contador", "Pacotes", "", "relatorios", "generate",
        lambda p: QDialog(p), "contador",
    )
    shell = NabiCodeShellWindow(
        Security(), (dashboard_module(), technical, extra), lambda: QMainWindow()
    )
    try:
        assert list(shell.navigation_buttons) == [item.module_id for item in LEGACY_NAVIGATION]
        assert list(shell.favorite_buttons) == ["contador"]
    finally:
        shell.close()


def test_sidebar_tem_scroll_largura_flexivel_e_nomes_integrais(qt_application):
    extras = tuple(
        AdministrativeModule(
            f"Área complementar com nome legível {index}", "Descrição", "",
            "dashboard", "view", lambda p: QDialog(p), f"extra-{index}",
        )
        for index in range(12)
    )
    shell = NabiCodeShellWindow(
        Security(), (dashboard_module(), *extras), lambda: QMainWindow()
    )
    try:
        shell.resize(1024, 680); shell.show(); qt_application.processEvents()
        assert shell.side_menu.minimumWidth() == 250
        assert shell.side_menu.maximumWidth() == 320
        assert shell.side_menu_scroll.widgetResizable() is True
        assert shell.side_menu_scroll.verticalScrollBar().maximum() > 0
        for module_id, button in shell.favorite_buttons.items():
            assert button.text() == button.toolTip()
            assert button.accessibleName() == button.text()
    finally:
        shell.close()


def test_customers_and_products_open_as_reused_maximized_windows(qt_application):
    created = []
    def factory(parent):
        dialog = QDialog(parent); created.append(dialog); return dialog
    customers = AdministrativeModule(
        "Clientes", "Cadastro", "F3", "clientes", "view", factory, "clientes"
    )
    products = AdministrativeModule(
        "Produtos", "Catálogo", "F4", "produtos", "view", factory, "produtos"
    )
    shell = NabiCodeShellWindow(
        Security(), (dashboard_module(), customers, products), lambda: QMainWindow()
    )
    try:
        assert shell.show_module("clientes") is True
        qt_application.processEvents()
        assert shell._wide_windows["clientes"] is created[0]
        assert created[0].isWindow() is True
        assert created[0].isMaximized() is True
        assert shell.show_module("clientes") is True
        assert len(created) == 1
        assert "border:3px solid #ffffff" in shell.navigation_buttons["clientes"].styleSheet()
        assert shell.show_module("produtos") is True
        qt_application.processEvents()
        assert created[1].isMaximized() is True
        created[1].reject(); qt_application.processEvents()
        assert shell._active_module == "dashboard"
    finally:
        shell.close()


def test_summary_cards_open_the_matching_authorized_customer_filter(qt_application):
    opened = []
    def filtered(parent, segment, title):
        opened.append((segment, title))
        return QDialog(parent)
    customers = AdministrativeModule(
        "Clientes", "Cadastro", "F3", "clientes", "view", lambda p: QDialog(p),
        "clientes", filtered_factory=filtered,
    )
    security = Security()
    shell = NabiCodeShellWindow(
        security, (dashboard_module(), customers), lambda: QMainWindow()
    )
    try:
        for key, expected in (
            ("total", "all"), ("current", "current"),
            ("owing", "owing"), ("alert", "alert"),
        ):
            assert shell.open_customer_segment(key) is True
            qt_application.processEvents()
            assert opened[-1][0] == expected
            assert shell._wide_windows["clientes"].property("customerSegment") == expected
        assert security.touches >= 4
    finally:
        shell.close()


def test_summary_card_arrows_move_focus_and_enter_keeps_single_action(qt_application):
    customers = AdministrativeModule(
        "Clientes", "Cadastro", "F3", "clientes", "view", lambda p: QDialog(p),
        "clientes", filtered_factory=lambda p, _segment, _title: QDialog(p),
    )
    shell = NabiCodeShellWindow(
        Security(), (dashboard_module(), customers), lambda: QMainWindow()
    )
    shell.open_customer_segment = Mock(return_value=True)
    try:
        shell.show(); shell.summary_labels["total"].setFocus(); qt_application.processEvents()
        down = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        assert shell.eventFilter(shell.summary_labels["total"], down) is True
        qt_application.processEvents(); assert shell.summary_labels["current"].hasFocus()
        enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        assert shell.eventFilter(shell.summary_labels["current"], enter) is True
        shell.open_customer_segment.assert_called_once_with("current")
    finally:
        shell.close()


def test_footer_actions_inherit_the_shell_theme(qt_application):
    shell = NabiCodeShellWindow(Security(), (dashboard_module(),), Mock())
    try:
        for button in (shell.help_button, shell.support_button, shell.panic_button):
            assert button.property("shellFooterAction") is True
            assert button.styleSheet() == ""
        assert 'QPushButton[shellFooterAction="true"]' in shell.styleSheet()
    finally:
        shell.close()


def test_navigation_arrows_move_focus_and_enter_activates_once(qt_application):
    pdv = QMainWindow()
    factory = Mock(return_value=pdv)
    shell = NabiCodeShellWindow(Security(), (dashboard_module(),), factory)
    try:
        shell.show(); shell.navigation_buttons["dashboard"].setFocus()
        qt_application.processEvents()
        right = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier
        )
        assert shell.eventFilter(shell.navigation_buttons["dashboard"], right) is True
        qt_application.processEvents()
        assert shell.navigation_buttons["vendas"].hasFocus()
        enter = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
        )
        assert shell.eventFilter(shell.navigation_buttons["vendas"], enter) is True
        factory.assert_called_once_with()
    finally:
        shell.close()


def test_secret_menu_requires_permission_and_administrative_password(qt_application):
    technical = AdministrativeModule(
        "Auditoria", "Acessos", "Ctrl+L", "technical", "audit",
        lambda p: QDialog(p), "auditoria", restricted_menu=True,
    )
    security = Mock()
    security.session = SimpleNamespace(user=SimpleNamespace(display_name="Administrador"))
    security.is_expired.return_value = False
    security.require.return_value = True
    security.confirm_manager_password.return_value = True
    shell = NabiCodeShellWindow(
        security, (dashboard_module(), technical), lambda: QMainWindow()
    )
    try:
        hub = Mock(spec=QDialog)
        with patch(
            "ui_qt.shell.main_window.QInputDialog.getText", return_value=("senha", True)
        ), patch("ui_qt.shell.main_window._create_administrative_hub", return_value=hub) as factory:
            assert shell.open_restricted_menu() is True
        security.require.assert_any_call("technical", "view")
        security.confirm_manager_password.assert_called_once_with("senha")
        assert factory.call_args.args[1] == (technical,)
        hub.exec.assert_called_once_with()

        security.require.return_value = False
        security.confirm_manager_password.reset_mock()
        with patch("ui_qt.shell.main_window.QInputDialog.getText") as password, patch(
            "ui_qt.shell.main_window.QMessageBox.warning"
        ):
            assert shell.open_restricted_menu() is False
        password.assert_not_called()
        security.confirm_manager_password.assert_not_called()

        security.require.return_value = True
        security.confirm_manager_password.return_value = False
        with patch(
            "ui_qt.shell.main_window.QInputDialog.getText", return_value=("errada", True)
        ), patch("ui_qt.shell.main_window._create_administrative_hub") as factory, patch(
            "ui_qt.shell.main_window.QMessageBox.warning"
        ):
            assert shell.open_restricted_menu() is False
        factory.assert_not_called()
    finally:
        shell.close()


def test_menu_restrito_inclui_todos_equivalentes_sem_mudar_permissoes(qt_application):
    modules = tuple(
        AdministrativeModule(
            label, "Descrição", "", permission_module, permission_action,
            lambda p: QDialog(p), module_id, restricted_menu=True,
        )
        for label, module_id, permission_module, permission_action in (
            ("Configurações", "configs", "configs", "view"),
            ("Ajuda", "ajuda", "dashboard", "view"),
            ("Central de Socorro", "socorro", "configs", "view"),
            ("Usuários", "usuarios", "technical", "users"),
            ("Auditoria", "auditoria", "technical", "audit"),
        )
    )
    security = Mock()
    security.session = SimpleNamespace(user=SimpleNamespace(display_name="Administrador"))
    security.is_expired.return_value = False
    security.require.return_value = True
    security.confirm_manager_password.return_value = True
    shell = NabiCodeShellWindow(
        security, (dashboard_module(), *modules), lambda: QMainWindow()
    )
    try:
        hub = Mock(spec=QDialog)
        with patch(
            "ui_qt.shell.main_window.QInputDialog.getText", return_value=("senha", True)
        ), patch("ui_qt.shell.main_window._create_administrative_hub", return_value=hub) as factory:
            assert shell.open_restricted_menu() is True
        selected = factory.call_args.args[1]
        assert tuple(module.module_id for module in selected) == (
            "configs", "ajuda", "socorro", "usuarios", "auditoria"
        )
        assert tuple(
            (module.permission_module, module.permission_action) for module in selected
        ) == (
            ("configs", "view"), ("dashboard", "view"), ("configs", "view"),
            ("technical", "users"), ("technical", "audit"),
        )
    finally:
        shell.close()


def test_apresentacao_nao_expoe_linguagem_interna_de_migracao(qt_application):
    shell = NabiCodeShellWindow(Security(), (dashboard_module(),), Mock())
    try:
        tooltip = shell.navigation_buttons["fiscal"].toolTip()
        assert "Legacy" not in tooltip
        assert "migração Qt" not in tooltip
        assert not hasattr(shell, "history_button")
    finally:
        shell.close()


def test_auditoria_legacy_preserva_as_doze_areas_sem_inventar_equivalentes_qt():
    source = Path("nabicode_legacy.py").read_text(encoding="utf-8")
    start = source.index("admin_sections = (")
    end = source.index("for nome, _icone, _descricao in admin_sections:", start)
    catalog = source[start:end]
    expected = (
        "Licença", "Banco de Dados", "Backup", "Atualizações",
        "Padrão de fábrica", "Diagnóstico", "Migração", "Demonstração",
        "Ferramentas", "Sistema", "Segurança", "Suporte",
    )
    assert all(f'(\"{name}\",' in catalog for name in expected)
    qt_modules = {"configs", "ajuda", "socorro", "usuarios", "auditoria"}
    assert qt_modules.isdisjoint({
        "licenca", "atualizacoes", "padrao_fabrica", "migracao", "demonstracao"
    })


def test_secret_menu_only_triggers_after_ten_clicks_inside_legacy_window(qt_application):
    shell = NabiCodeShellWindow(Security(), (dashboard_module(),), Mock())
    shell.open_restricted_menu = Mock(return_value=True)
    try:
        with patch("ui_qt.shell.main_window.time.monotonic", side_effect=[1.0 + i / 10 for i in range(10)]):
            assert [shell._logo_clicked() for _ in range(9)] == [False] * 9
            assert shell._logo_clicked() is True
        shell.open_restricted_menu.assert_called_once_with()

        shell.open_restricted_menu.reset_mock()
        with patch("ui_qt.shell.main_window.time.monotonic", side_effect=[10.0,10.1,16.0]+[16.1+i/10 for i in range(8)]):
            assert [shell._logo_clicked() for _ in range(11)] == [False] * 11
        shell.open_restricted_menu.assert_not_called()
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
            assert shell.nabi_assistant.widget() is panel
            assert shell.nabi_assistant.isExpanded() is False
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
        owing_value=Decimal("12345.50"), alert_count=2,
        alert_value=Decimal("1080.75"),
    )
    shell = NabiCodeShellWindow(
        Security(), (summary_module(lambda: values),), lambda: QMainWindow()
    )
    try:
        deadline = time.monotonic() + 2
        while "12" not in shell.summary_labels["total"].text() and time.monotonic() < deadline:
            qt_application.processEvents(); time.sleep(0.01)
        assert shell.summary_labels["total"].text() == "Total de Fichas: 12"
        assert "R$ 12.345,50" in shell.summary_labels["owing"].text()
        assert "R$ 1.080,75" in shell.summary_labels["alert"].text()
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
