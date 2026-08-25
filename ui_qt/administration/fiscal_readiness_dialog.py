from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)


STYLE = """
QDialog{background:#0d1117;color:#f0f6fc;font-size:14px} QLabel{color:#f0f6fc}
QPushButton{background:#30363d;color:#f0f6fc;border:0;border-radius:7px;
min-height:42px;padding:0 14px;font-weight:800}
QPushButton:focus{border:3px solid #ffffff}
"""


class FiscalReadinessDialog(QDialog):
    """Central Fiscal Qt informativa; não oferece nenhuma operação SEFAZ."""

    STATE_LABELS = {
        "BLOQUEADO": "Configuração incompleta",
        "AGUARDA_VERIFICACAO_MANUAL": "Aguardando verificação manual",
    }

    def __init__(self, application, parent=None) -> None:
        super().__init__(parent)
        self.application = application
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("Central Fiscal — prontidão")
        self.resize(1120, 720)
        self.setMinimumSize(920, 600)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("CENTRAL FISCAL — CONFIGURAÇÃO E PRONTIDÃO")
        title.setStyleSheet("font-size:24px;font-weight:900;color:#ff5263")
        root.addWidget(title)
        warning = QLabel(
            "Esta tela é somente informativa. Não transmite, não autoriza documentos "
            "e não solicita a senha do certificado."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "background:#241317;border-left:6px solid #ff293d;padding:12px;font-weight:800"
        )
        root.addWidget(warning)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        body = QWidget(); self.content = QVBoxLayout(body); self.content.setSpacing(12)
        scroll.setWidget(body); root.addWidget(scroll, 1)
        actions = QHBoxLayout(); actions.addStretch()
        self.configure_button = QPushButton("Configurar Fiscal")
        self.refresh_button = QPushButton("Atualizar leitura  [F5]")
        self.close_button = QPushButton("Fechar  [Esc]")
        self.configure_button.clicked.connect(self.configure)
        self.refresh_button.clicked.connect(self.reload)
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.configure_button); actions.addWidget(self.refresh_button); actions.addWidget(self.close_button)
        root.addLayout(actions)
        for widget in (self.configure_button, self.refresh_button, self.close_button):
            widget.installEventFilter(self)
        self._f5 = QShortcut(QKeySequence("F5"), self)
        self._f5.setAutoRepeat(False); self._f5.activated.connect(self.reload)
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.setAutoRepeat(False); self._escape.activated.connect(self.reject)
        self.reload()

    def configure(self) -> bool:
        dialog = FiscalConfigurationDialog(self.application, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        return self.reload()

    def _clear(self) -> None:
        def discard(item) -> None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                return
            layout = item.layout()
            if layout is not None:
                while layout.count():
                    discard(layout.takeAt(0))
                layout.deleteLater()

        while self.content.count():
            discard(self.content.takeAt(0))

    def reload(self) -> bool:
        try:
            snapshot = self.application.snapshot()
        except Exception as error:
            QMessageBox.warning(self, "Central Fiscal", str(error))
            return False
        self._clear()
        state = QLabel(self.STATE_LABELS.get(snapshot.state, "Bloqueado com segurança"))
        state.setStyleSheet("font-size:20px;font-weight:900;color:#ffb454")
        self.content.addWidget(state)
        summary = QGridLayout()
        values = (
            ("Ambiente", snapshot.environment),
            ("Módulo habilitado", "Sim" if snapshot.enabled else "Não"),
            ("CNPJ emitente", snapshot.issuer_document),
            ("UF", snapshot.issuer_state),
            ("Regime", snapshot.tax_regime),
            ("Certificado A1", snapshot.certificate_name if snapshot.certificate_configured else "Não configurado ou indisponível"),
        )
        for row, (label, value) in enumerate(values):
            heading = QLabel(label); heading.setStyleSheet("color:#8b949e;font-weight:800")
            data = QLabel(str(value)); data.setTextFormat(Qt.TextFormat.PlainText)
            data.setStyleSheet("font-size:16px;font-weight:800")
            summary.addWidget(heading, row, 0); summary.addWidget(data, row, 1)
        self.content.addLayout(summary)
        for model in snapshot.models:
            lines = [
                f"{model.label} — {'habilitado' if model.enabled else 'não habilitado'}",
                (
                    f"Numeração preparada; próximo número: {model.next_number}"
                    if model.numbering_initialized else "Numeração ainda não preparada"
                ),
            ]
            lines.extend(f"• {problem}" for problem in model.local_problems)
            card = QLabel("\n".join(lines)); card.setWordWrap(True)
            card.setTextFormat(Qt.TextFormat.PlainText)
            card.setStyleSheet(
                "background:#161b22;border:1px solid #30363d;border-left:6px solid #ff5263;"
                "border-radius:8px;padding:12px;font-size:15px"
            )
            self.content.addWidget(card)
        notice = QLabel("\n".join(f"• {text}" for text in snapshot.notices))
        notice.setWordWrap(True); notice.setTextFormat(Qt.TextFormat.PlainText)
        notice.setStyleSheet("color:#c9d1d9;padding:8px")
        self.content.addWidget(notice)
        self.content.addStretch()
        return True

    def eventFilter(self, watched, event) -> bool:
        operational = (self.configure_button, self.refresh_button, self.close_button)
        if watched in operational and event.type() == QEvent.Type.KeyPress:
            if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return super().eventFilter(watched, event)
            event.accept()
            if event.isAutoRepeat():
                return True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                previous = {
                    self.configure_button: self.close_button,
                    self.refresh_button: self.configure_button,
                    self.close_button: self.refresh_button,
                }
                target = previous[watched]
                target.setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.configure_button:
                self.configure()
            elif watched is self.refresh_button:
                self.reload()
            else:
                self.reject()
            return True
        return super().eventFilter(watched, event)


class FiscalConfigurationDialog(QDialog):
    """Configuração explícita de homologação; nunca transmite ou persiste senha."""

    def __init__(self, application, parent=None) -> None:
        super().__init__(parent)
        self.application = application
        self.setWindowTitle("Configurar Fiscal — HOMOLOGAÇÃO")
        self.setMinimumSize(760, 700)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(STYLE)
        config = application.configuration()
        issuer = dict(config.get("issuer") or {})
        root = QVBoxLayout(self)
        warning = QLabel(
            "AMBIENTE DE HOMOLOGAÇÃO — SEM VALOR FISCAL. Revise todos os dados. "
            "Nenhum documento será transmitido nesta etapa."
        )
        warning.setWordWrap(True); warning.setStyleSheet("color:#ffb454;font-weight:900")
        root.addWidget(warning)
        form = QFormLayout(); root.addLayout(form)
        self.cnpj = QLineEdit(str(config.get("cnpj") or ""))
        self.name = QLineEdit(str(issuer.get("name") or ""))
        self.ie = QLineEdit(str(issuer.get("state_registration") or ""))
        self.state = QComboBox(); self.state.addItems(sorted(application._fiscal.STATE_CODES))
        self.state.setCurrentText(str(config.get("state") or "BA"))
        self.regime = QComboBox(); self.regime.addItems(application._fiscal.TAX_REGIME_LABELS)
        self.regime.setCurrentText(str(config.get("tax_regime") or "SIMPLES_NACIONAL"))
        self.city_code = QLineEdit(str(issuer.get("city_code") or ""))
        self.city = QLineEdit(str(issuer.get("city") or ""))
        self.street = QLineEdit(str(issuer.get("street") or ""))
        self.number = QLineEdit(str(issuer.get("number") or ""))
        self.district = QLineEdit(str(issuer.get("district") or ""))
        self.zip_code = QLineEdit(str(issuer.get("zip_code") or ""))
        for label, widget in (
            ("CNPJ", self.cnpj), ("Razão social", self.name),
            ("Inscrição estadual", self.ie), ("UF", self.state),
            ("Regime tributário", self.regime), ("Código IBGE do município", self.city_code),
            ("Município", self.city), ("Logradouro", self.street),
            ("Número", self.number), ("Bairro", self.district), ("CEP", self.zip_code),
        ): form.addRow(label, widget)
        self.model55 = QCheckBox("NF-e modelo 55"); self.model55.setChecked("55" in config.get("enabled_models", ()))
        self.model65 = QCheckBox("NFC-e modelo 65"); self.model65.setChecked("65" in config.get("enabled_models", ()))
        models = QHBoxLayout(); models.addWidget(self.model55); models.addWidget(self.model65); models.addStretch()
        form.addRow("Modelos", models)
        self.default_model = QComboBox(); self.default_model.addItems(["55", "65"])
        self.default_model.setCurrentText(str(config.get("default_model") or "65")); form.addRow("Modelo padrão", self.default_model)
        self.series55 = QSpinBox(); self.series55.setRange(0, 999); self.series55.setValue(int(config.get("sale_series_55", 1)))
        self.series65 = QSpinBox(); self.series65.setRange(0, 999); self.series65.setValue(int(config.get("sale_series_65", 1)))
        form.addRow("Série NF-e 55", self.series55); form.addRow("Série NFC-e 65", self.series65)
        certificate_row = QHBoxLayout(); self.certificate = QLineEdit(str(config.get("certificate_path") or "")); self.certificate.setReadOnly(True)
        self.browse_button = QPushButton("Selecionar A1"); self.browse_button.clicked.connect(self._browse)
        certificate_row.addWidget(self.certificate, 1); certificate_row.addWidget(self.browse_button); form.addRow("Certificado .pfx/.p12", certificate_row)
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Senha do certificado", self.password)
        actions = QHBoxLayout(); actions.addStretch()
        self.cancel_button = QPushButton("Cancelar [Esc]"); self.save_button = QPushButton("Revisar e salvar")
        self.cancel_button.clicked.connect(self.reject); self.save_button.clicked.connect(self._save)
        actions.addWidget(self.cancel_button); actions.addWidget(self.save_button); root.addLayout(actions)
        for widget in (self.browse_button, self.cancel_button, self.save_button):
            widget.installEventFilter(self)
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.setAutoRepeat(False); self._escape.activated.connect(self.reject)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar certificado A1", "", "Certificado A1 (*.pfx *.p12)")
        if path: self.certificate.setText(path)

    def _values(self) -> dict:
        return {
            "cnpj": self.cnpj.text(), "issuer_name": self.name.text(),
            "state_registration": self.ie.text(), "state": self.state.currentText(),
            "tax_regime": self.regime.currentText(), "city_code": self.city_code.text(),
            "city": self.city.text(), "street": self.street.text(), "number": self.number.text(),
            "district": self.district.text(), "zip_code": self.zip_code.text(),
            "model_55": self.model55.isChecked(), "model_65": self.model65.isChecked(),
            "default_model": self.default_model.currentText(),
            "sale_series_55": self.series55.value(), "sale_series_65": self.series65.value(),
            "certificate_path": self.certificate.text(),
        }

    def _save(self) -> None:
        values = self._values()
        models = ", ".join(model for model in ("55", "65") if values[f"model_{model}"]) or "nenhum"
        review = (
            f"Ambiente: HOMOLOGAÇÃO\nCNPJ: {values['cnpj']}\nUF: {values['state']}\n"
            f"Regime: {values['tax_regime']}\nModelos: {models}\n"
            f"Certificado: {Path(values['certificate_path']).name}\n\nSalvar esta configuração?"
        )
        if QMessageBox.question(self, "Revisar configuração fiscal", review) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.application.configure_homologation(values, password=self.password.text())
        except Exception as error:
            QMessageBox.warning(self, "Configuração fiscal", str(error)); self.password.clear(); self.password.setFocus(); return
        self.password.clear()
        QMessageBox.information(self, "Configuração fiscal", "Configuração de homologação salva. Nenhuma transmissão foi realizada.")
        self.accept()

    def eventFilter(self, watched, event) -> bool:
        browse_button = getattr(self, "browse_button", None)
        cancel_button = getattr(self, "cancel_button", None)
        save_button = getattr(self, "save_button", None)
        operational = tuple(
            button for button in (browse_button, cancel_button, save_button)
            if button is not None
        )
        if watched in operational and event.type() == QEvent.Type.KeyPress:
            if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return super().eventFilter(watched, event)
            event.accept()
            if event.isAutoRepeat():
                return True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                previous = {
                    browse_button: save_button,
                    cancel_button: browse_button,
                    save_button: cancel_button,
                }
                previous[watched].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is browse_button:
                self._browse()
            elif watched is cancel_button:
                self.reject()
            else:
                self._save()
            return True
        return super().eventFilter(watched, event)
