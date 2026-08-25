from __future__ import annotations

from dataclasses import dataclass
import time

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget, QInputDialog,
)

from commercial.domain.money import MoneyCodec


def _create_administrative_hub(security, modules, parent, **kwargs):
    # Import tardio: o shell também é usado durante a composição da aplicação.
    from ui_qt.administration.module_hub import AdministrativeModuleHub
    return AdministrativeModuleHub(security, modules, parent, **kwargs)


@dataclass(frozen=True, slots=True)
class LegacyNavigationItem:
    module_id: str
    label: str
    shortcut: str
    color: str
    hover_color: str
    icon: str


# Contrato do Legacy: permissões e módulos opcionais jamais reordenam estes slots.
LEGACY_NAVIGATION = (
    LegacyNavigationItem("dashboard", "Início", "F1", "#1f6feb", "#1158c7", "▥"),
    LegacyNavigationItem("vendas", "Vendas", "F2", "#2ea043", "#238636", "▣"),
    LegacyNavigationItem("clientes", "Clientes", "F3", "#8957e5", "#6e40c9", "●"),
    LegacyNavigationItem("produtos", "Produtos", "F4", "#bf8700", "#9e6a03", "◆"),
    LegacyNavigationItem("financeiro", "Financeiro", "", "#0f766e", "#115e59", "$"),
    LegacyNavigationItem("caixa", "Caixa", "", "#a16207", "#854d0e", "▤"),
    LegacyNavigationItem("fiscal", "Central Fiscal", "", "#7c3aed", "#6d28d9", "▧"),
    LegacyNavigationItem("relatorios", "Relatórios", "", "#0369a1", "#075985", "▥"),
    LegacyNavigationItem("configs", "Configs", "F5", "#da3633", "#b62324", "⚙"),
)


SHELL_STYLE = """
QMainWindow, QWidget#shellRoot { background:#0d1117; color:#f0f6fc; }
QFrame#sideMenu { background:#161b22; border:0; }
QLabel { color:#f0f6fc; }
QPushButton { color:#f0f6fc; border:0; border-radius:12px; min-height:44px;
 font-size:14px; font-weight:800; padding:0 12px; }
QPushButton:focus { border:3px solid #ffffff; }
QPushButton:disabled { color:#8b949e; background:#21262d; }
QPushButton[shellFooterAction="true"] {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
 stop:0 #314354,stop:0.12 #22303d,stop:1 #101821);
 border:1px solid #42576a; border-left:5px solid #00d084;
 border-bottom:4px solid #071019; text-align:left;
}
QPushButton[shellFooterAction="true"]:hover { border-top:2px solid #00e5ff; }
QPushButton[shellFooterAction="true"]:pressed { background:#09111a; border-bottom:1px solid #071019; }
QPushButton#panicAction { border-left:5px solid #ff3b5c; }
QPushButton#summaryCard {
 background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
 stop:0 #303a46,stop:0.18 #202833,stop:1 #11161d);
 border:1px solid #3b4654; border-left:5px solid #00d084;
 border-radius:8px; min-height:42px; padding:8px 10px;
 font-size:13px; font-weight:800; text-align:left;
}
QPushButton#summaryCard:hover { border-top:2px solid #00e5ff; }
"""


NAVIGATION_SUBTITLES = {
    "dashboard": "Visão geral e movimento do dia",
    "vendas": "PDV, pagamentos e comprovantes",
    "clientes": "Cadastro, fichas e recebimentos",
    "produtos": "Catálogo, preços e estoque",
    "financeiro": "Contas, cobranças e resultados",
    "caixa": "Abertura, movimento e fechamento",
    "fiscal": "Documentos e comunicação fiscal",
    "relatorios": "Consultas e impressão",
    "configs": "Empresa, usuários e preferências",
}

NEON_ACCENTS = {
    "dashboard": ("#00e5ff", "#0077b6"),
    "vendas": ("#2f9bff", "#0059b3"),
    "clientes": ("#00f0ff", "#007c91"),
    "produtos": ("#70d7ff", "#126e96"),
    "financeiro": ("#00d9ff", "#006d8f"),
    "caixa": ("#3f8cff", "#174ea6"),
    "fiscal": ("#ff293d", "#971525"),
    "relatorios": ("#00b8ff", "#00628a"),
    "configs": ("#ff3b5c", "#a31330"),
}


class _SummarySignals(QObject):
    completed = Signal(int, object, object)


class _SummaryWorker(QRunnable):
    def __init__(self, generation, loader):
        super().__init__(); self.generation = generation; self.loader = loader
        self.signals = _SummarySignals()

    @Slot()
    def run(self):
        try: result, error = self.loader(), None
        except Exception as caught: result, error = None, caught
        self.signals.completed.emit(self.generation, result, error)


class NabiCodeShellWindow(QMainWindow):
    """Janela principal com a mesma hierarquia operacional do NabiCode Legacy."""

    WIDE_PRIMARY_MODULES = frozenset({"clientes", "produtos"})
    CUSTOMER_SEGMENTS = {
        "total": ("all", "TODOS OS CLIENTES"),
        "current": ("current", "CLIENTES EM DIA"),
        "owing": ("owing", "CLIENTES DEVENDO"),
        "alert": ("alert", "ATRASADOS HÁ MAIS DE 60 DIAS"),
    }

    def __init__(
        self, security, modules, pdv_factory, *, store_name="NabiCode",
        profile_label="COMERCIAL / NÃO FISCAL", reauthenticate=None, parent=None,
    ) -> None:
        super().__init__(parent)
        self.security = security
        self.modules = tuple(modules)
        self.pdv_factory = pdv_factory
        self.reauthenticate = reauthenticate
        self._reauthenticating = False
        self._modules = {m.module_id: m for m in self.modules if m.module_id}
        self._open_dialogs = {}
        self._module_pages = {}
        self._wide_windows = {}
        self._pdv_window = None
        self._shortcuts = []
        self._summary_generation = 0
        self._summary_workers = []
        self._logo_clicks = 0
        self._last_logo_click = 0.0
        self.worker_pool = QThreadPool(self)
        self.worker_pool.setMaxThreadCount(2)
        self._active_module = "dashboard"
        self.setWindowTitle(f"NabiCode — {store_name}")
        self.resize(1360, 820)
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(SHELL_STYLE)
        root = QWidget(objectName="shellRoot")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        self.side_menu = self._build_side_menu(); layout.addWidget(self.side_menu)
        body = QWidget(); body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 10, 18, 12); body_layout.setSpacing(10)
        body_layout.addLayout(self._build_header(store_name, profile_label))
        body_layout.addLayout(self._build_navigation())
        self.pages = QStackedWidget(objectName="shellPages"); body_layout.addWidget(self.pages, 1)
        layout.addWidget(body, 1)
        self._install_shortcuts(); self.show_module("dashboard")

    def _build_side_menu(self):
        frame = QFrame(objectName="sideMenu"); frame.setFixedWidth(300)
        root = QVBoxLayout(frame); root.setContentsMargins(14, 20, 14, 16); root.setSpacing(10)
        self.logo = QLabel("NABICODE"); self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setAccessibleName("NabiCode")
        self.logo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logo.setStyleSheet("color:#00d084;font-size:25px;font-weight:900;padding:10px;letter-spacing:1px")
        self.logo.installEventFilter(self)
        root.addWidget(self.logo); self.summary_labels = {}
        for key, text, accent, color in (
            ("total", "Fichas: —", "#8b949e", "#ffffff"),
            ("current", "Em Dia: —", "#2ea043", "#5df2a1"),
            ("owing", "Devendo: —", "#bf8700", "#ffd866"),
            ("alert", "Alerta (>60d): —", "#da3633", "#ff8582"),
        ):
            label = QPushButton(text, objectName="summaryCard")
            label.setAccessibleName(text)
            label.setProperty("summaryAccent", accent)
            label.setStyleSheet(f"QPushButton{{color:{color};border-left:5px solid {accent}}}")
            label.installEventFilter(self)
            label.clicked.connect(
                lambda _checked=False, selected=key: self.open_customer_segment(selected)
            )
            root.addWidget(label); self.summary_labels[key] = label
        shortcuts = QLabel("ATALHOS RÁPIDOS\n\n[F1]  Início\n[F2]  Vendas\n[F3]  Clientes\n[F4]  Produtos\n[F5]  Configs\n[Ctrl+Shift+P]  Pânico")
        shortcuts.setStyleSheet("background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:12px;font-size:13px;font-weight:700;color:#c9d1d9")
        root.addWidget(shortcuts)
        favorites = QLabel("FAVORITOS"); favorites.setStyleSheet("background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:11px;font-size:14px;font-weight:800")
        root.addWidget(favorites)
        self.favorite_buttons = {}
        canonical = {item.module_id for item in LEGACY_NAVIGATION}
        for module in self.modules:
            if module.module_id in canonical or module.module_id in {"ajuda"}:
                continue
            button = QPushButton(module.label)
            button.setAccessibleName(module.label)
            button.setStyleSheet("background:#21262d;text-align:left;min-height:34px")
            button.clicked.connect(
                lambda _checked=False, selected=module.module_id: self.open_module(selected)
            )
            root.addWidget(button)
            self.favorite_buttons[module.module_id] = button
        root.addStretch()
        self.help_button = QPushButton("Central de Ajuda"); self.help_button.setProperty("shellFooterAction", True)
        self.help_button.clicked.connect(lambda: self.open_module("ajuda")); root.addWidget(self.help_button)
        self.support_button = QPushButton("Ajuda / suporte"); self.support_button.setProperty("shellFooterAction", True)
        self.support_button.clicked.connect(lambda: self.open_module("ajuda")); root.addWidget(self.support_button)
        self.panic_button = QPushButton("Pânico  [Ctrl+Shift+P]", objectName="panicAction"); self.panic_button.setProperty("shellFooterAction", True)
        self.panic_button.clicked.connect(self.close); root.addWidget(self.panic_button)
        footer = QLabel("NabiCode"); footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color:#8b949e;font-size:10px"); root.addWidget(footer)
        return frame

    def _build_header(self, store_name, profile_label):
        row = QHBoxLayout(); row.setSpacing(12); self.menu_toggle = QPushButton("Menu  ✕")
        self.menu_toggle.setStyleSheet("background:#161b22"); self.menu_toggle.clicked.connect(self.toggle_side_menu)
        row.addWidget(self.menu_toggle)
        title = QLabel(str(store_name).upper()); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#00d084;font-size:25px;font-weight:900;letter-spacing:1px"); row.addWidget(title, 1)
        profile = QLabel(profile_label); profile.setStyleSheet("color:#8b949e;font-size:12px;font-weight:700"); row.addWidget(profile)
        self.history_button = QPushButton("Histórico"); self.history_button.setStyleSheet("background:#161b22")
        self.history_button.clicked.connect(lambda: self.open_module("auditoria")); row.addWidget(self.history_button)
        return row

    def _build_navigation(self):
        grid = QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(10)
        grid.setContentsMargins(0, 6, 0, 8); self.navigation_buttons = {}
        self._navigation_items = {item.module_id: item for item in LEGACY_NAVIGATION}
        for index, item in enumerate(LEGACY_NAVIGATION):
            shortcut = f" [{item.shortcut}]" if item.shortcut else ""
            subtitle = NAVIGATION_SUBTITLES[item.module_id]
            button = QPushButton(f"{item.label}{shortcut}\n{subtitle}")
            button.setFixedHeight(82)
            button.setObjectName(f"navigation_{item.module_id}"); button.setAccessibleName(item.label)
            button.setProperty("legacyOrder", index)
            self._style_navigation_button(button, item, active=False)
            button.clicked.connect(lambda _checked=False, selected=item.module_id: self.show_module(selected))
            button.installEventFilter(self); grid.addWidget(button, index // 3, index % 3)
            self.navigation_buttons[item.module_id] = button
        available = {"dashboard", "vendas"}.union(self._modules)
        for module_id, button in self.navigation_buttons.items():
            button.setEnabled(module_id in available)
            if module_id not in available:
                tooltip = (
                    "Disponível somente no NabiCode oficial Legacy; migração Qt pendente"
                    if module_id == "fiscal" else "Módulo indisponível nesta edição"
                )
                button.setToolTip(tooltip)
        return grid

    def _install_shortcuts(self):
        for key, module_id in (("F1", "dashboard"), ("F2", "vendas"), ("F3", "clientes"), ("F4", "produtos"), ("F5", "configs")):
            shortcut = QShortcut(QKeySequence(key), self); shortcut.setAutoRepeat(False)
            shortcut.activated.connect(lambda selected=module_id: self.show_module(selected)); self._shortcuts.append(shortcut)
        panic = QShortcut(QKeySequence("Ctrl+Shift+P"), self); panic.setAutoRepeat(False)
        panic.activated.connect(self.close); self._shortcuts.append(panic)

    def toggle_side_menu(self):
        visible = not self.side_menu.isVisible(); self.side_menu.setVisible(visible)
        self.menu_toggle.setText("Menu  ✕" if visible else "Menu  ➜")

    def _authorized(self, module):
        self._authorize_permission(
            module.permission_module, module.permission_action, module.label
        )

    def _authorize_permission(self, permission_module, permission_action, label):
        session = getattr(self.security, "session", None)
        if session is None or self.security.is_expired():
            if self.reauthenticate is None or self._reauthenticating:
                raise PermissionError("Sessão expirada. Entre novamente.")
            self._reauthenticating = True
            try:
                authenticated = bool(self.reauthenticate(self))
            finally:
                self._reauthenticating = False
            session = getattr(self.security, "session", None)
            if not authenticated or session is None or self.security.is_expired():
                raise PermissionError("Autenticação cancelada. A ação permanece bloqueada.")
        if not self.security.require(permission_module, permission_action):
            raise PermissionError(f"Seu perfil não possui permissão para abrir {label}.")
        self.security.touch()

    def _mark_active(self, module_id):
        self._active_module = module_id
        for selected, button in self.navigation_buttons.items():
            self._style_navigation_button(
                button, self._navigation_items[selected], active=selected == module_id
            )
        button = self.navigation_buttons.get(module_id)
        if button is not None: button.setFocus(Qt.FocusReason.OtherFocusReason)

    @staticmethod
    def _style_navigation_button(button, item, *, active):
        accent, shadow = NEON_ACCENTS[item.module_id]
        border = "3px solid #ffffff" if active else "1px solid rgba(255,255,255,35)"
        button.setStyleSheet(
            "QPushButton{"
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {accent},stop:0.045 #30404d,stop:0.13 #1b2632,"
            "stop:0.62 #111923,stop:1 #080d14);"
            f"border:{border};border-left:6px solid {accent};"
            f"border-bottom:6px solid {shadow};border-radius:14px;"
            "font-size:15px;font-weight:900;text-align:left;padding:8px 16px 12px 16px}"
            "QPushButton:hover{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {accent},stop:0.08 #435464,stop:0.45 #1c2a38,stop:1 #0b131d);"
            f"border-top:3px solid {accent}}}"
            "QPushButton:pressed{"
            "background:#09111a;"
            f"border-left:6px solid {accent};border-bottom:2px solid {shadow};"
            "padding-top:12px;padding-bottom:8px}"
            f"QPushButton:focus{{border:3px solid #ffffff;border-left:6px solid {accent};"
            f"border-bottom:6px solid {shadow}}}"
            "QPushButton:disabled{background:#21262d;color:#8b949e;"
            "border:1px solid #30363d;border-bottom:5px solid #161b22}"
        )

    def show_module(self, module_id):
        if module_id == "vendas": return self.open_pdv()
        if module_id == "dashboard":
            module = self._modules.get("dashboard")
            if module is None or module.embedded_factory is None: return False
            try:
                self._authorized(module)
                if self.pages.count() == 0: self.pages.addWidget(module.embedded_factory(self.pages))
                self.pages.setCurrentIndex(0); self._mark_active("dashboard")
                self.refresh_summary(); return True
            except Exception as error:
                QMessageBox.warning(self, "Início", str(error)); return False
        if module_id in {
            "clientes", "produtos", "financeiro", "caixa", "fiscal",
            "relatorios", "configs",
        }:
            return self.open_primary_module(module_id)
        return self.open_module(module_id)

    def open_primary_module(self, module_id):
        """Exibe módulos principais dentro do shell, como as telas do Legacy."""

        module = self._modules.get(module_id)
        if module is None:
            return False
        try:
            self._authorized(module)
            if module_id in self.WIDE_PRIMARY_MODULES:
                return self._show_wide_module(module_id, module.factory)
            page = self._module_pages.get(module_id)
            if page is None:
                page = module.factory(self.pages)
                if not isinstance(page, QDialog):
                    raise TypeError("O módulo deve fornecer uma tela Qt.")
                page.setModal(False)
                page.setWindowFlags(Qt.WindowType.Widget)
                page.finished.connect(
                    lambda _result, selected=module_id: self._primary_page_closed(selected)
                )
                self.pages.addWidget(page)
                self._module_pages[module_id] = page
            self.pages.setCurrentWidget(page)
            page.show()
            self._mark_active(module_id)
            return True
        except Exception as error:
            QMessageBox.warning(self, module.label, str(error))
            return False

    def _show_wide_module(self, module_id, factory, *, segment=""):
        current = self._wide_windows.get(module_id)
        if current is not None and current.isVisible():
            if str(current.property("customerSegment") or "") == segment:
                current.showMaximized(); current.raise_(); current.activateWindow()
                self._mark_active(module_id)
                return True
            current.close()
        dialog = factory(self)
        if not isinstance(dialog, QDialog):
            raise TypeError("O módulo deve fornecer uma janela Qt.")
        dialog.setModal(False)
        dialog.setProperty("customerSegment", segment)
        self._wide_windows[module_id] = dialog
        dialog.finished.connect(
            lambda _result, selected=module_id, opened=dialog:
            self._wide_module_closed(selected, opened)
        )
        dialog.showMaximized(); dialog.raise_(); dialog.activateWindow()
        self._mark_active(module_id)
        return True

    def _wide_module_closed(self, module_id, dialog):
        if self._wide_windows.get(module_id) is dialog:
            self._wide_windows.pop(module_id, None)
        if self._active_module == module_id:
            self.show_module("dashboard")

    def open_customer_segment(self, summary_key):
        module = self._modules.get("clientes")
        segment_data = self.CUSTOMER_SEGMENTS.get(str(summary_key))
        if module is None or module.filtered_factory is None or segment_data is None:
            return False
        segment, title = segment_data
        try:
            self._authorized(module)
            return self._show_wide_module(
                "clientes",
                lambda parent: module.filtered_factory(parent, segment, title),
                segment=segment,
            )
        except Exception as error:
            QMessageBox.warning(self, module.label, str(error))
            return False

    def _logo_clicked(self):
        now = time.monotonic()
        if now - self._last_logo_click > 5.0:
            self._logo_clicks = 0
        self._last_logo_click = now
        self._logo_clicks += 1
        if self._logo_clicks < 10:
            return False
        self._logo_clicks = 0
        return self.open_restricted_menu()

    def open_restricted_menu(self):
        try:
            self._authorize_permission("technical", "view", "Menu Técnico")
        except Exception as error:
            QMessageBox.warning(self, "Acesso negado", str(error))
            return False
        password, accepted = QInputDialog.getText(
            self, "Acesso ao Menu Técnico", "Digite a senha administrativa:",
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return False
        confirm = getattr(self.security, "confirm_manager_password", None)
        if not callable(confirm) or not confirm(password):
            QMessageBox.warning(self, "Acesso negado", "Senha administrativa incorreta.")
            return False
        technical_modules = tuple(
            module for module in self.modules if module.permission_module == "technical"
        )
        if not technical_modules:
            QMessageBox.information(
                self, "Menu Técnico", "Nenhum módulo técnico está disponível nesta edição."
            )
            return False
        hub = _create_administrative_hub(
            self.security, technical_modules, self,
            window_title="Menu Técnico NabiCode", heading="MENU TÉCNICO NABICODE",
        )
        hub.exec()
        return True

    def _primary_page_closed(self, module_id):
        if self._active_module == module_id:
            self.show_module("dashboard")

    def open_module(self, module_id):
        module = self._modules.get(module_id)
        if module is None:
            QMessageBox.information(self, "NabiCode", "Este módulo ainda não está disponível nesta edição."); return False
        if module_id in self._open_dialogs: return False
        try:
            self._authorized(module); dialog = module.factory(self)
            if not isinstance(dialog, QDialog): raise TypeError("O módulo deve abrir uma janela Qt.")
            self._open_dialogs[module_id] = dialog; self._mark_active(module_id); dialog.exec(); return True
        except Exception as error:
            QMessageBox.warning(self, module.label, str(error)); return False
        finally:
            self._open_dialogs.pop(module_id, None); self._mark_active("dashboard")

    def open_pdv(self):
        if self._pdv_window is not None and self._pdv_window.isVisible():
            self._pdv_window.raise_(); self._pdv_window.activateWindow(); return False
        try:
            window = self.pdv_factory()
            if not isinstance(window, QMainWindow): raise TypeError("A tela de Vendas deve ser uma janela Qt.")
            self._pdv_window = window; window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            window.destroyed.connect(self._pdv_closed); self._mark_active("vendas"); window.showMaximized(); return True
        except Exception as error:
            self._pdv_window = None; QMessageBox.warning(self, "Vendas", str(error)); return False

    def _pdv_closed(self, *_args):
        self._pdv_window = None; self.show_module("dashboard"); self.raise_(); self.activateWindow()

    def ensure_pdv(self):
        self.open_pdv(); return self._pdv_window

    def refresh_summary(self):
        module = self._modules.get("dashboard")
        loader = getattr(module, "summary_loader", None) if module is not None else None
        if loader is None:
            self._summary_unavailable("Indisponível")
            return
        self._summary_generation += 1
        generation = self._summary_generation
        for label in self.summary_labels.values(): label.setText("Carregando...")
        worker = _SummaryWorker(generation, loader)
        worker.signals.completed.connect(self._summary_loaded)
        self._summary_workers.append(worker); self.worker_pool.start(worker)

    def _summary_loaded(self, generation, summary, error):
        self._summary_workers = [w for w in self._summary_workers if w.generation != generation]
        if generation != self._summary_generation: return
        if error is not None or summary is None:
            self._summary_unavailable("Indisponível")
            return
        self.summary_labels["total"].setText(f"Total de Fichas: {summary.total_records}")
        self.summary_labels["current"].setText(f"Em Dia: {summary.current_count}")
        self.summary_labels["owing"].setText(
            f"Devendo ({summary.owing_count}): R$ {MoneyCodec.format_br(summary.owing_value)}"
        )
        self.summary_labels["alert"].setText(
            f"Alerta >60d ({summary.alert_count}): R$ {MoneyCodec.format_br(summary.alert_value)}"
        )

    def _summary_unavailable(self, value):
        self.summary_labels["total"].setText(f"Fichas: {value}")
        self.summary_labels["current"].setText(f"Em Dia: {value}")
        self.summary_labels["owing"].setText(f"Devendo: {value}")
        self.summary_labels["alert"].setText(f"Alerta (>60d): {value}")

    def eventFilter(self, watched, event):
        if watched is getattr(self, "logo", None) and event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                event.accept(); self._logo_clicked(); return True
        navigation_buttons = getattr(self, "navigation_buttons", {})
        summary_buttons = tuple(getattr(self, "summary_labels", {}).values())
        if watched in summary_buttons and event.type() == QEvent.Type.KeyPress and event.key() in {
            Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Up, Qt.Key.Key_Down,
        }:
            event.accept()
            if event.isAutoRepeat(): return True
            index = summary_buttons.index(watched)
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                watched.click()
            else:
                delta = -1 if event.key() in {
                    Qt.Key.Key_Up, Qt.Key.Key_Return, Qt.Key.Key_Enter,
                } else 1
                target = max(0, min(len(summary_buttons) - 1, index + delta))
                summary_buttons[target].setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        if watched in navigation_buttons.values() and event.type() == QEvent.Type.KeyPress and event.key() in {
            Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Left,
            Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
        }:
            event.accept()
            if event.isAutoRepeat(): return True
            key = event.key()
            if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                watched.click()
            else:
                ordered = tuple(navigation_buttons.values())
                if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                    enabled = tuple(button for button in ordered if button.isEnabled())
                    index = enabled.index(watched)
                    enabled[max(0, index - 1)].setFocus(Qt.FocusReason.OtherFocusReason)
                else:
                    index = ordered.index(watched)
                    row, column = divmod(index, 3)
                    row_step, column_step = {
                        Qt.Key.Key_Left: (0, -1), Qt.Key.Key_Right: (0, 1),
                        Qt.Key.Key_Up: (-1, 0), Qt.Key.Key_Down: (1, 0),
                    }[key]
                    while True:
                        row += row_step; column += column_step
                        if not (0 <= row < 3 and 0 <= column < 3): break
                        candidate = ordered[row * 3 + column]
                        if candidate.isEnabled():
                            candidate.setFocus(Qt.FocusReason.OtherFocusReason); break
            return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        self._summary_generation += 1
        if self._pdv_window is not None: self._pdv_window.close()
        for dialog in tuple(self._open_dialogs.values()): dialog.close()
        for dialog in tuple(self._wide_windows.values()): dialog.close()
        for page in tuple(self._module_pages.values()): page.close()
        self.worker_pool.clear()
        self.worker_pool.waitForDone(3000)
        super().closeEvent(event)
