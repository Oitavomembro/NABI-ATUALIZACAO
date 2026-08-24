from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.ui_preferences import UIPreferencesService


STYLE = """
QDialog { background:#0d1117; color:#f0f6fc; font-size:14px; }
QLabel, QCheckBox { color:#f0f6fc; }
QLineEdit, QComboBox, QTextEdit { background:#161b22; color:#f0f6fc;
 border:1px solid #30363d; border-radius:6px; min-height:30px; padding:4px 8px; }
QPushButton { background:#21262d; color:#f0f6fc; border:1px solid #30363d;
 border-radius:7px; min-height:34px; padding:5px 12px; font-weight:700; }
QPushButton:focus { border:2px solid #58a6ff; }
QPushButton#primary { background:#238636; }
QTabWidget::pane { border:1px solid #30363d; }
QTabBar::tab { background:#161b22; color:#c9d1d9; padding:9px 16px; }
QTabBar::tab:selected { color:#00d084; border-bottom:2px solid #00d084; }
"""


class SettingsDialog(QDialog):
    """Configurações não fiscais, com organização equivalente ao Legacy."""

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Configurações do NabiCode")
        self.resize(780, 600)
        self.setMinimumSize(680, 520)
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        title = QLabel("CONFIGURAÇÕES E PERSONALIZAÇÃO")
        title.setStyleSheet("font-size:22px;font-weight:900;color:#00d084")
        root.addWidget(title)
        self.identity = QLabel()
        self.identity.setStyleSheet("color:#8b949e")
        root.addWidget(self.identity)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_interface_tab()
        self._build_backup_tab()
        self._build_diagnostics_tab()

        close = QPushButton("Fechar [Esc]")
        close.clicked.connect(self.reject)
        root.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.setAutoRepeat(False)
        self._escape.activated.connect(self.reject)
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)
        self._load()

    def _build_interface_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        self.mode = QComboBox(); self.mode.addItems(UIPreferencesService.MODES)
        self.workspace = QComboBox(); self.workspace.addItems(UIPreferencesService.WORKSPACES)
        self.density = QComboBox(); self.density.addItems(UIPreferencesService.DENSITIES)
        self.theme = QComboBox(); self.theme.addItems(UIPreferencesService.THEMES)
        self.adaptive = QCheckBox("Adaptar módulos ao espaço de trabalho")
        self.background = QCheckBox("Exibir imagem de fundo")
        form.addRow("Modo de interface", self.mode)
        form.addRow("Espaço de trabalho", self.workspace)
        form.addRow("Densidade", self.density)
        form.addRow("Tema oficial", self.theme)
        form.addRow("", self.adaptive)
        form.addRow("", self.background)
        self.save_interface = QPushButton("Salvar e aplicar")
        self.save_interface.setObjectName("primary")
        self.save_interface.clicked.connect(self._save_preferences)
        form.addRow("", self.save_interface)
        self.tabs.addTab(page, "Interface")

    def _build_backup_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "Backup do banco comercial. Nenhum certificado, senha ou configuração fiscal é incluído."
        ))
        self.local_backup = QLineEdit()
        self.cloud_backup = QLineEdit()
        for title, field in (
            ("Pasta principal", self.local_backup),
            ("Pasta sincronizada adicional (opcional)", self.cloud_backup),
        ):
            layout.addWidget(QLabel(title))
            row = QHBoxLayout(); row.addWidget(field, 1)
            choose = QPushButton("Escolher…")
            choose.clicked.connect(lambda _=False, target=field: self._choose_directory(target))
            row.addWidget(choose); layout.addLayout(row)
        self.daily = QCheckBox("Criar um backup por dia ao abrir o sistema")
        layout.addWidget(self.daily)
        buttons = QHBoxLayout()
        self.save_backup = QPushButton("Salvar destinos")
        self.save_backup.clicked.connect(self._save_backup)
        self.backup_now = QPushButton("Fazer backup agora")
        self.backup_now.setObjectName("primary")
        self.backup_now.clicked.connect(self._create_backup)
        buttons.addWidget(self.save_backup); buttons.addWidget(self.backup_now)
        layout.addLayout(buttons); layout.addStretch(1)
        self.tabs.addTab(page, "Backup")

    def _build_diagnostics_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        self.diagnostic_text = QTextEdit(); self.diagnostic_text.setReadOnly(True)
        self.diagnostic_text.setPlaceholderText(
            "O diagnóstico verifica banco, espaço, pastas e backup sem alterar dados de negócio."
        )
        layout.addWidget(self.diagnostic_text, 1)
        self.run_diagnostic = QPushButton("Executar diagnóstico")
        self.run_diagnostic.clicked.connect(self._run_diagnostics)
        layout.addWidget(self.run_diagnostic)
        self.tabs.addTab(page, "Diagnóstico")

    def _load(self) -> None:
        try:
            snapshot = self.service.load()
        except Exception as error:
            QMessageBox.warning(self, "Configurações", str(error))
            self.reject(); return
        self.identity.setText(f"Preferências do usuário: {snapshot.username}")
        values = snapshot.preferences
        self.mode.setCurrentText(values["mode"])
        self.workspace.setCurrentText(values["workspace"])
        self.density.setCurrentText(values["density"])
        self.theme.setCurrentText(values["theme"])
        self.adaptive.setChecked(bool(values["adaptive_menu"]))
        self.background.setChecked(bool(values["background_enabled"]))
        directories = snapshot.backup_directories
        self.local_backup.setText(directories[0] if directories else "")
        self.cloud_backup.setText(directories[1] if len(directories) > 1 else "")
        self.daily.setChecked(snapshot.daily_backup_enabled)
        editable = self.service.can("edit")
        for widget in (
            self.mode, self.workspace, self.density, self.theme, self.adaptive,
            self.background, self.local_backup, self.cloud_backup, self.daily,
            self.save_interface, self.save_backup,
        ):
            widget.setEnabled(editable)
        self.backup_now.setEnabled(self.service.can("backup"))
        self.run_diagnostic.setEnabled(self.service.can("diagnose"))
        self.mode.setFocus(Qt.FocusReason.OtherFocusReason)

    def _save_preferences(self) -> None:
        try:
            current = dict(self.service.load().preferences)
            current.update({
                "mode": self.mode.currentText(),
                "workspace": self.workspace.currentText(),
                "density": self.density.currentText(),
                "theme": self.theme.currentText(),
                "adaptive_menu": self.adaptive.isChecked(),
                "background_enabled": self.background.isChecked(),
            })
            self.service.save_preferences(current)
            QMessageBox.information(self, "Configurações", "Preferências salvas para este usuário.")
        except Exception as error:
            QMessageBox.warning(self, "Configurações", str(error))

    def _choose_directory(self, target: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Escolher pasta de backup", target.text())
        if selected:
            target.setText(selected); target.setFocus(Qt.FocusReason.OtherFocusReason)

    def _save_backup(self) -> None:
        try:
            self.service.configure_backup(
                local_directory=self.local_backup.text(),
                cloud_directory=self.cloud_backup.text(),
                daily=self.daily.isChecked(),
            )
            QMessageBox.information(self, "Backup", "Destinos de backup salvos.")
        except Exception as error:
            QMessageBox.warning(self, "Backup", str(error))
            self.local_backup.setFocus(Qt.FocusReason.OtherFocusReason)

    def _create_backup(self) -> None:
        try:
            result = self.service.create_backup()
            QMessageBox.information(
                self, "Backup concluído",
                "Arquivos criados:\n" + "\n".join(result.created),
            )
        except Exception as error:
            QMessageBox.warning(self, "Backup", str(error))
        self.backup_now.setFocus(Qt.FocusReason.OtherFocusReason)

    def _run_diagnostics(self) -> None:
        try:
            _result, report = self.service.run_diagnostics()
            self.diagnostic_text.setPlainText(report)
        except Exception as error:
            QMessageBox.warning(self, "Diagnóstico", str(error))
        self.run_diagnostic.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
            and event.isAutoRepeat()
        ):
            event.accept(); return True
        return super().eventFilter(watched, event)
