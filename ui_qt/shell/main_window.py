from __future__ import annotations

import json
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QRunnable, QSettings, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from commercial.domain.money import MoneyCodec
from services.ui_preferences import UIPreferencesService


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

    def __init__(
        self, security, modules, pdv_factory, *, store_name="NabiCode",
        profile_label="COMERCIAL / NÃO FISCAL", reauthenticate=None,
        ux_settings=None, parent=None,
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
        # Widgets may deliver focus/style events while the shell is still being
        # assembled. Keep the event filter safe throughout that construction.
        self.navigation_buttons = {}
        self._pdv_window = None
        self._shortcuts = []
        self._summary_generation = 0
        self._summary_workers = []
        self.worker_pool = QThreadPool(self)
        self.worker_pool.setMaxThreadCount(2)
        self._active_module = "dashboard"
        self._ux_settings = ux_settings or QSettings("NabiCode", "NabiCode-UX")
        self._ux_user_key = self._current_user_key()
        self._ui_preferences = self._load_ux_preferences()
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
        body_layout.addWidget(self._build_module_search())
        body_layout.addLayout(self._build_navigation())
        self.pages = QStackedWidget(objectName="shellPages"); body_layout.addWidget(self.pages, 1)
        layout.addWidget(body, 1)
        self._apply_ui_preferences(); self._refresh_favorites()
        self._install_shortcuts(); self.show_module("dashboard")

    def _current_user_key(self):
        session = getattr(self.security, "session", None)
        user = getattr(session, "user", None)
        value = getattr(user, "username", "") or getattr(user, "display_name", "")
        try:
            return UIPreferencesService.user_key(value)
        except ValueError:
            return "sessao"

    def _load_ux_preferences(self):
        raw = self._ux_settings.value(f"users/{self._ux_user_key}/preferences", "{}")
        try:
            values = json.loads(str(raw or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            values = {}
        return UIPreferencesService.normalize(values)

    def _save_ux_preferences(self):
        self._ux_settings.setValue(
            f"users/{self._ux_user_key}/preferences",
            json.dumps(self._ui_preferences, ensure_ascii=False, sort_keys=True),
        )

    def _apply_ui_preferences(self):
        point_size = int(self._ui_preferences.get("font_size", 12))
        font = QFont(self.font()); font.setPointSize(point_size); self.setFont(font)
        height = {"Compacta": 70, "Normal": 82, "Confortável": 94}.get(
            self._ui_preferences.get("density"), 82
        )
        for button in self.navigation_buttons.values(): button.setFixedHeight(height)

    def apply_ui_preferences(self, values):
        """Aplica somente preferências visuais normalizadas e locais do operador."""
        self._ui_preferences = UIPreferencesService.normalize(values)
        self._save_ux_preferences(); self._apply_ui_preferences(); self._refresh_favorites()

    def _module_is_authorized_now(self, module_id):
        session = getattr(self.security, "session", None)
        if session is None or self.security.is_expired(): return False
        if module_id == "vendas": return True
        module = self._modules.get(module_id)
        if module is None: return False
        try: return bool(self.security.require(module.permission_module, module.permission_action))
        except Exception: return False

    def _visible_authorized_modules(self):
        visible = []
        for item in LEGACY_NAVIGATION:
            button = self.navigation_buttons.get(item.module_id)
            if button is not None and button.isEnabled() and self._module_is_authorized_now(item.module_id):
                visible.append((item.module_id, item.label, NAVIGATION_SUBTITLES[item.module_id]))
        canonical = {item.module_id for item in LEGACY_NAVIGATION}
        for module in self.modules:
            if module.module_id in canonical or not module.module_id: continue
            button = getattr(self, "auxiliary_buttons", {}).get(module.module_id)
            if button is not None and not button.isHidden() and self._module_is_authorized_now(module.module_id):
                visible.append((module.module_id, module.label, module.description))
        return tuple(visible)

    def _build_module_search(self):
        frame = QFrame(); layout = QVBoxLayout(frame); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(3)
        self.module_search = QLineEdit(); self.module_search.setPlaceholderText("Buscar módulo autorizado…")
        self.module_search.setAccessibleName("Busca de módulos autorizados")
        self.module_results = QListWidget(); self.module_results.setMaximumHeight(130); self.module_results.hide()
        self.module_search.textChanged.connect(self._refresh_module_search)
        self.module_search.installEventFilter(self); self.module_results.installEventFilter(self)
        self.module_results.itemDoubleClicked.connect(lambda *_args: self._open_selected_search_result())
        layout.addWidget(self.module_search); layout.addWidget(self.module_results)
        return frame

    def _refresh_module_search(self, text):
        term = str(text or "").strip().casefold(); self.module_results.clear()
        if not term:
            self.module_results.hide(); return
        for module_id, label, description in self._visible_authorized_modules():
            if term not in f"{label} {description}".casefold(): continue
            item = QListWidgetItem(f"{label} — {description}")
            item.setData(Qt.ItemDataRole.UserRole, module_id); self.module_results.addItem(item)
        self.module_results.setVisible(self.module_results.count() > 0)
        if self.module_results.count(): self.module_results.setCurrentRow(0)

    def _open_selected_search_result(self):
        item = self.module_results.currentItem()
        if item is None: return False
        module_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self.module_search.clear(); self.module_results.hide()
        return self.show_module(module_id) if module_id in self.navigation_buttons else self.open_module(module_id)

    def _toggle_active_favorite(self):
        module_id = self._active_module
        if not self._module_is_authorized_now(module_id): return False
        self._ui_preferences = UIPreferencesService.toggle_favorite(self._ui_preferences, module_id)
        self._save_ux_preferences(); self._refresh_favorites(); return True

    def _refresh_favorites(self):
        while self.favorites_layout.count():
            item = self.favorites_layout.takeAt(0)
            if item.widget() is not None: item.widget().deleteLater()
        available = {module_id: label for module_id, label, _description in self._visible_authorized_modules()}
        requested = UIPreferencesService.favorites(self._ui_preferences)
        allowed = tuple(module_id for module_id in requested if module_id in available)
        if allowed != requested:
            self._ui_preferences = dict(self._ui_preferences); self._ui_preferences["favorites"] = list(allowed)
            self._save_ux_preferences()
        # Preserve the public compatibility view used by the existing shell:
        # auxiliary authorized modules remain discoverable here even though
        # their visual section is now correctly labelled "Outros módulos".
        self.favorite_buttons = dict(getattr(self, "auxiliary_buttons", {}))
        for module_id in allowed:
            button = QPushButton(available[module_id]); button.setAccessibleName(available[module_id])
            button.setStyleSheet("background:#21262d;text-align:left;min-height:34px")
            button.clicked.connect(lambda _checked=False, selected=module_id: self.show_module(selected) if selected in self.navigation_buttons else self.open_module(selected))
            self.favorites_layout.addWidget(button); self.favorite_buttons[module_id] = button

    def _build_auxiliary_modules(self):
        canonical = {item.module_id for item in LEGACY_NAVIGATION}
        self.auxiliary_buttons = {}
        for module in self.modules:
            if not module.module_id or module.module_id in canonical: continue
            if not self._module_is_authorized_now(module.module_id): continue
            button = QPushButton(module.label); button.setAccessibleName(module.label)
            button.setStyleSheet("background:#21262d;text-align:left;min-height:34px")
            button.clicked.connect(lambda _checked=False, selected=module.module_id: self.open_module(selected))
            self.auxiliary_layout.addWidget(button); self.auxiliary_buttons[module.module_id] = button

    def _build_side_menu(self):
        frame = QFrame(objectName="sideMenu"); frame.setFixedWidth(300)
        root = QVBoxLayout(frame); root.setContentsMargins(14, 20, 14, 16); root.setSpacing(10)
        logo = QLabel("NABICODE"); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("color:#00d084;font-size:25px;font-weight:900;padding:10px;letter-spacing:1px")
        root.addWidget(logo); self.summary_labels = {}
        for key, text, accent, color in (
            ("total", "Fichas: —", "#8b949e", "#ffffff"),
            ("current", "Em Dia: —", "#2ea043", "#5df2a1"),
            ("owing", "Devendo: —", "#bf8700", "#ffd866"),
            ("alert", "Alerta (>60d): —", "#da3633", "#ff8582"),
        ):
            label = QLabel(text)
            label.setMinimumHeight(42)
            label.setStyleSheet(
                "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                "stop:0 #303a46,stop:0.18 #202833,stop:1 #11161d);"
                f"color:{color};border:1px solid #3b4654;border-left:5px solid {accent};"
                "border-radius:8px;padding:10px;font-size:13px;font-weight:800"
            )
            root.addWidget(label); self.summary_labels[key] = label
        shortcuts = QLabel("ATALHOS RÁPIDOS\n\n[F1]  Início\n[F2]  Vendas\n[F3]  Clientes\n[F4]  Produtos\n[F5]  Configs\n[Ctrl+Shift+P]  Pânico")
        shortcuts.setStyleSheet("background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:12px;font-size:13px;font-weight:700;color:#c9d1d9")
        root.addWidget(shortcuts)
        auxiliary = QLabel("OUTROS MÓDULOS"); auxiliary.setStyleSheet("background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:11px;font-size:14px;font-weight:800")
        root.addWidget(auxiliary)
        auxiliary_container = QWidget(); self.auxiliary_layout = QVBoxLayout(auxiliary_container)
        self.auxiliary_layout.setContentsMargins(0, 0, 0, 0); self.auxiliary_layout.setSpacing(5)
        root.addWidget(auxiliary_container); self._build_auxiliary_modules()
        favorites = QLabel("FAVORITOS"); favorites.setStyleSheet("background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:11px;font-size:14px;font-weight:800")
        root.addWidget(favorites)
        favorite_container = QWidget(); self.favorites_layout = QVBoxLayout(favorite_container)
        self.favorites_layout.setContentsMargins(0, 0, 0, 0); self.favorites_layout.setSpacing(5)
        root.addWidget(favorite_container)
        self.favorite_toggle_button = QPushButton("☆ Favoritar módulo atual")
        self.favorite_toggle_button.clicked.connect(self._toggle_active_favorite); root.addWidget(self.favorite_toggle_button)
        self.favorite_buttons = {}
        root.addStretch()
        self.help_button = QPushButton("Central de Ajuda"); self.help_button.setStyleSheet("background:#1f6feb")
        self.help_button.clicked.connect(lambda: self.open_module("ajuda")); root.addWidget(self.help_button)
        self.support_button = QPushButton("Ajuda / suporte"); self.support_button.setStyleSheet("background:#2ea043")
        self.support_button.clicked.connect(lambda: self.open_module("ajuda")); root.addWidget(self.support_button)
        self.panic_button = QPushButton("Pânico  [Ctrl+Shift+P]"); self.panic_button.setStyleSheet("background:#b62324")
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
        self.status_notification = QLabel("")
        self.status_notification.setStyleSheet("color:#aeb5bb;font-size:12px;font-weight:700")
        row.addWidget(self.status_notification)
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
        if not self.security.require(module.permission_module, module.permission_action):
            raise PermissionError(f"Seu perfil não possui permissão para abrir {module.label}.")
        self.security.touch()

    def _mark_active(self, module_id):
        self._active_module = module_id
        for selected, button in self.navigation_buttons.items():
            self._style_navigation_button(
                button, self._navigation_items[selected], active=selected == module_id
            )
        button = self.navigation_buttons.get(module_id)
        if button is not None: button.setFocus(Qt.FocusReason.OtherFocusReason)
        if hasattr(self, "favorite_toggle_button"):
            favorite = module_id in UIPreferencesService.favorites(self._ui_preferences)
            self.favorite_toggle_button.setText(("★ Remover favorito" if favorite else "☆ Favoritar módulo atual"))

    def _notify_known_state(self, text):
        """Exibe somente estado já concluído; nunca antecipa sucesso."""
        self.status_notification.setText(str(text or ""))

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
                self._notify_known_state("Início aberto")
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
            self._notify_known_state(f"{module.label} aberto")
            return True
        except Exception as error:
            QMessageBox.warning(self, module.label, str(error))
            return False

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
            self._open_dialogs[module_id] = dialog; self._mark_active(module_id); dialog.exec()
            self._notify_known_state(f"{module.label} fechado"); return True
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
            window.destroyed.connect(self._pdv_closed); self._mark_active("vendas"); window.showMaximized()
            self._notify_known_state("Vendas aberto"); return True
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
        if watched in {getattr(self, "module_search", None), getattr(self, "module_results", None)} and event.type() == QEvent.Type.KeyPress:
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                event.accept()
                if event.isAutoRepeat(): return True
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.module_search.setFocus(Qt.FocusReason.BacktabFocusReason); return True
                if watched is self.module_search and self.module_results.count() != 1:
                    if self.module_results.count(): self.module_results.setFocus(Qt.FocusReason.TabFocusReason)
                    return True
                self._open_selected_search_result(); return True
            if event.key() == Qt.Key.Key_Escape:
                event.accept(); self.module_search.clear(); self.module_results.hide(); self.module_search.setFocus(); return True
        if watched in getattr(self, "navigation_buttons", {}).values() and event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            if event.isAutoRepeat(): return True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: watched.focusPreviousChild()
            else: watched.click()
            return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        self._summary_generation += 1
        if self._pdv_window is not None: self._pdv_window.close()
        for dialog in tuple(self._open_dialogs.values()): dialog.close()
        for page in tuple(self._module_pages.values()): page.close()
        self.worker_pool.clear()
        self.worker_pool.waitForDone(3000)
        super().closeEvent(event)
