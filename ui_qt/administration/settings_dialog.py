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
        self._build_printing_tab()
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
            "Backup do banco e dos documentos fiscais. Certificados, senhas e e-mails não são incluídos."
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

    def _build_printing_tab(self) -> None:
        page = QWidget(); form = QFormLayout(page)
        self.document_outputs = {}
        for label, category, printer_key in (
            ("Recibo / venda", "recibo", "impressora_recibo"),
            ("Entrega", "entrega", "impressora_entrega"),
            ("Ficha do cliente", "ficha", "impressora_ficha"),
            ("Histórico", "historico", "impressora_historico"),
            ("Fechamento de caixa", "fechamento", "impressora_historico"),
        ):
            printer = QComboBox()
            output_format = QComboBox()
            output_format.addItems(("Cupom 80 mm", "A4", "PDF virtual"))
            row = QHBoxLayout(); row.addWidget(printer, 2); row.addWidget(output_format, 1)
            form.addRow(label, row)
            self.document_outputs[category] = (printer_key, printer, output_format)
        self.printer = self.document_outputs["recibo"][1]
        self.output_format = self.document_outputs["recibo"][2]
        self.receipt_model = QComboBox()
        from services.receipt_template_service import ReceiptTemplateService
        self.receipt_model.addItems(ReceiptTemplateService.names())
        self.print_font = QComboBox(); self.print_font.addItems(("Helvetica", "Times-Roman", "Courier"))
        self.font_size = QComboBox(); self.font_size.addItems(tuple(str(value) for value in range(6, 25)))
        self.auto_cut = QCheckBox("Corte automático em impressora térmica")
        self.cut_type = QComboBox(); self.cut_type.addItems(("PARCIAL", "TOTAL"))
        self.cut_lines = QComboBox(); self.cut_lines.addItems(tuple(str(value) for value in range(13)))
        form.addRow("Modelo visual", self.receipt_model); form.addRow("Fonte", self.print_font)
        form.addRow("Tamanho", self.font_size); form.addRow("", self.auto_cut)
        form.addRow("Tipo do corte", self.cut_type); form.addRow("Linhas antes do corte", self.cut_lines)
        self.receipt_preview = QTextEdit(); self.receipt_preview.setReadOnly(True); form.addRow("Prévia", self.receipt_preview)
        row = QHBoxLayout(); self.refresh_preview = QPushButton("Atualizar prévia"); self.save_printing = QPushButton("Salvar impressão")
        self.save_printing.setObjectName("primary"); self.refresh_preview.clicked.connect(self._preview_receipt); self.save_printing.clicked.connect(self._save_printing)
        row.addWidget(self.refresh_preview); row.addWidget(self.save_printing); form.addRow("", row)
        self.tabs.addTab(page, "Impressão")

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
        try:
            printing = self.service.load_printing(); values = printing.values
            for category, (printer_key, printer, output_format) in self.document_outputs.items():
                printer.addItems(printing.printers)
                printer.setCurrentText(values[printer_key])
                output_format.setCurrentText(values[f"formato_impressao_{category}"])
            self.receipt_model.setCurrentText(values["modelo_cupom_visual"]); self.print_font.setCurrentText(values["impressao_fonte"])
            self.font_size.setCurrentText(values["impressao_fonte_tamanho"]); self.auto_cut.setChecked(values["impressao_corte_automatico"] == "1")
            self.cut_type.setCurrentText(values["impressao_tipo_corte"]); self.cut_lines.setCurrentText(values["impressao_linhas_antes_corte"])
            self._preview_receipt()
        except Exception as error:
            self.receipt_preview.setPlainText(str(error))
        editable = self.service.can("edit")
        for widget in (
            self.mode, self.workspace, self.density, self.theme, self.adaptive,
            self.background, self.local_backup, self.cloud_backup, self.daily,
            self.save_interface, self.save_backup,
            *(widget for _key, printer, output_format in self.document_outputs.values() for widget in (printer, output_format)),
            self.receipt_model, self.print_font,
            self.font_size, self.auto_cut, self.cut_type, self.cut_lines, self.save_printing,
        ):
            widget.setEnabled(editable)
        self.backup_now.setEnabled(self.service.can("backup"))
        self.run_diagnostic.setEnabled(self.service.can("diagnose"))
        self.mode.setFocus(Qt.FocusReason.OtherFocusReason)

    def _preview_receipt(self) -> None:
        try: self.receipt_preview.setPlainText(self.service.preview_receipt(self.receipt_model.currentText()))
        except Exception as error: self.receipt_preview.setPlainText(str(error))

    def _save_printing(self) -> None:
        try:
            current = dict(self.service.load_printing().values)
            for category, (printer_key, printer, output_format) in self.document_outputs.items():
                current[printer_key] = printer.currentText()
                current[f"formato_impressao_{category}"] = output_format.currentText()
            current.update({"modelo_cupom_visual": self.receipt_model.currentText(), "impressao_fonte": self.print_font.currentText(), "impressao_fonte_tamanho": self.font_size.currentText(), "impressao_corte_automatico": "1" if self.auto_cut.isChecked() else "0", "impressao_tipo_corte": self.cut_type.currentText(), "impressao_linhas_antes_corte": self.cut_lines.currentText()})
            self.service.save_printing(current); QMessageBox.information(self, "Impressão", "Configuração de impressão salva.")
        except Exception as error: QMessageBox.warning(self, "Impressão", str(error))

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
        ):
            if event.isAutoRepeat():
                event.accept(); return True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                previous = watched.previousInFocusChain()
                if previous is not None:
                    previous.setFocus(Qt.FocusReason.BacktabFocusReason)
                event.accept(); return True
        return super().eventFilter(watched, event)
