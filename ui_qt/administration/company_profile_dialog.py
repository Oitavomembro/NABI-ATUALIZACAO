from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Callable

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from services.company_profile_service import (
    CompanyActivity, CompanyProfileDraft, CompanyProfileService, CompanyProfileVersion,
)


class CompanyProfileDialog(QDialog):
    """Onboarding/revisão empresarial; não habilita Fiscal nem substitui licença/permissões."""

    def __init__(
        self, service: CompanyProfileService, parent=None,
        *, notifier: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self._notifier = notifier or self._show_message
        self._reviewed: CompanyProfileDraft | None = None
        self._baseline_version = 0
        self._loading = False
        self._confirming = False
        self.setWindowTitle("Perfil empresarial do NabiCode")
        self.setModal(True)
        self.resize(880, 760)

        root = QVBoxLayout(self)
        title = QLabel("PERFIL EMPRESARIAL")
        title.setStyleSheet("font-size:24px;font-weight:900;color:#00d084")
        root.addWidget(title)
        separation = QLabel(
            "Licença libera a edição do NabiCode; permissões definem quem pode alterar; "
            "este perfil registra dados empresariais confirmados. São controles separados."
        )
        separation.setWordWrap(True)
        separation.setStyleSheet("font-size:14px;font-weight:700;padding:8px;background:#20262e")
        root.addWidget(separation)
        self.readiness_label = QLabel()
        self.readiness_label.setWordWrap(True)
        self.readiness_label.setStyleSheet("color:#ffd166;font-weight:700")
        root.addWidget(self.readiness_label)

        self.form_page = QWidget()
        form = QFormLayout(self.form_page)
        self.cnpj = QLineEdit(); self.cnpj.setMaxLength(18)
        self.legal_name = QLineEdit(); self.legal_name.setMaxLength(180)
        self.tax_regime = QComboBox()
        for value, label in (
            ("MEI", "MEI"), ("SIMPLES_NACIONAL", "Simples Nacional"),
            ("LUCRO_PRESUMIDO", "Lucro Presumido"), ("LUCRO_REAL", "Lucro Real"),
            ("OUTRO", "Outro / confirmar com responsável"),
        ):
            self.tax_regime.addItem(label, value)
        self.classification = QComboBox()
        for value in ("MEI", "ME", "EPP", "OUTRO"):
            self.classification.addItem(value, value)
        self.activities = QPlainTextEdit()
        self.activities.setPlaceholderText(
            "Um CNAE por linha: 4711302 | Comércio varejista | PRINCIPAL"
        )
        self.activities.setMaximumHeight(90)
        self.state = QComboBox()
        for value in sorted(service.STATES): self.state.addItem(value, value)
        self.city = QLineEdit(); self.city.setMaxLength(100)
        self.state_registration = QLineEdit(); self.state_registration.setMaxLength(30)
        self.municipal_registration = QLineEdit(); self.municipal_registration.setMaxLength(30)
        self.operation_types = QLineEdit()
        self.operation_types.setPlaceholderText("Ex.: VAREJO, SERVICO")
        self.document_types = QLineEdit()
        self.document_types.setPlaceholderText("Ex.: NFE, NFCE (não habilita emissão)")
        self.source = QLineEdit(); self.source.setMaxLength(180)
        self.source.setPlaceholderText("Documento ou fonte conferida pelo responsável")
        self.source_date = self._date_edit()
        self.effective_from = self._date_edit()
        self.change_reason = QLineEdit(); self.change_reason.setMaxLength(240)
        self.change_reason.setPlaceholderText("Motivo da criação ou alteração (mínimo 10 caracteres)")
        for label, field in (
            ("CNPJ confirmado*", self.cnpj), ("Razão social*", self.legal_name),
            ("Regime tributário*", self.tax_regime), ("Enquadramento*", self.classification),
            ("CNAEs", self.activities), ("UF*", self.state), ("Município*", self.city),
            ("Inscrição estadual", self.state_registration),
            ("Inscrição municipal", self.municipal_registration),
            ("Tipos de operação", self.operation_types),
            ("Documentos aplicáveis", self.document_types), ("Fonte confirmada*", self.source),
            ("Data da fonte*", self.source_date), ("Vigência inicial*", self.effective_from),
            ("Motivo da confirmação*", self.change_reason),
        ):
            form.addRow(label, field)
        root.addWidget(self.form_page)

        actions = QHBoxLayout()
        self.legacy_button = QPushButton("Carregar configuração antiga como rascunho")
        self.review_button = QPushButton("Revisar perfil [Enter]")
        self.review_button.setStyleSheet("min-height:38px;font-weight:800")
        actions.addWidget(self.legacy_button); actions.addStretch(); actions.addWidget(self.review_button)
        root.addLayout(actions)

        self.review_panel = QWidget(); self.review_panel.setVisible(False)
        review_layout = QVBoxLayout(self.review_panel)
        review_title = QLabel("REVISÃO OBRIGATÓRIA — confira antes de confirmar")
        review_title.setStyleSheet("font-size:18px;font-weight:900;color:#ffd166")
        self.review_summary = QPlainTextEdit(); self.review_summary.setReadOnly(True)
        self.review_summary.setMinimumHeight(190)
        self.review_ack = QCheckBox(
            "Conferi a fonte e os dados. Entendo que isto NÃO habilita Fiscal/SEFAZ."
        )
        review_layout.addWidget(review_title); review_layout.addWidget(self.review_summary)
        review_layout.addWidget(self.review_ack)
        root.addWidget(self.review_panel)

        bottom = QHBoxLayout()
        self.back_button = QPushButton("Voltar e editar [Shift+Enter]")
        self.confirm_button = QPushButton("Confirmar perfil")
        self.confirm_button.setEnabled(False)
        self.confirm_button.setStyleSheet("background:#238636;color:white;min-height:40px;font-weight:900")
        self.close_button = QPushButton("Fechar [Esc]")
        bottom.addWidget(self.close_button); bottom.addStretch()
        bottom.addWidget(self.back_button); bottom.addWidget(self.confirm_button)
        root.addLayout(bottom)

        self.legacy_button.clicked.connect(self.load_legacy_draft)
        self.review_button.clicked.connect(self.review)
        self.back_button.clicked.connect(self._back_to_form)
        self.review_ack.toggled.connect(self._sync_confirmation)
        self.confirm_button.clicked.connect(self.confirm)
        self.close_button.clicked.connect(self.reject)
        self._editable = (
            self.cnpj, self.legal_name, self.tax_regime, self.classification, self.activities,
            self.state, self.city, self.state_registration, self.municipal_registration,
            self.operation_types, self.document_types, self.source, self.source_date,
            self.effective_from, self.change_reason,
        )
        for widget in self._editable:
            signal = getattr(widget, "textChanged", None) or getattr(widget, "currentIndexChanged", None) or getattr(widget, "dateChanged", None)
            signal.connect(self._invalidate_review)
        self._navigation = self._editable + (
            self.legacy_button, self.review_button, self.review_ack, self.back_button,
            self.confirm_button, self.close_button,
        )
        for widget in self._navigation: widget.installEventFilter(self)
        self._load_current_or_empty()
        self.cnpj.setFocus(Qt.FocusReason.OtherFocusReason)

    @staticmethod
    def _date_edit() -> QDateEdit:
        field = QDateEdit(QDate.currentDate())
        field.setDisplayFormat("dd/MM/yyyy"); field.setCalendarPopup(True)
        return field

    def _show_message(self, kind: str, message: str) -> None:
        method = QMessageBox.information if kind == "info" else QMessageBox.warning
        method(self, "Perfil empresarial", message)

    def _load_current_or_empty(self) -> None:
        try:
            history = self.service.history()
            self._baseline_version = history[-1].version if history else 0
            if history: self._populate(history[-1])
            readiness = self.service.readiness()
            missing = ", ".join(readiness.missing_fields) or "nenhum"
            self.readiness_label.setText(
                f"Readiness informativo: {readiness.status} · pendências: {missing} · "
                "enables_fiscal=false"
            )
        except Exception as error:
            self.readiness_label.setText(f"Leitura bloqueada: {error} · enables_fiscal=false")

    def _populate(self, value: CompanyProfileDraft | CompanyProfileVersion) -> None:
        self._loading = True
        try:
            self.cnpj.setText(value.cnpj); self.legal_name.setText(value.legal_name)
            self.tax_regime.setCurrentIndex(max(0, self.tax_regime.findData(value.tax_regime)))
            self.classification.setCurrentIndex(max(0, self.classification.findData(value.business_classification)))
            self.activities.setPlainText("\n".join(
                f"{item.cnae} | {item.description}" + (" | PRINCIPAL" if item.primary else "")
                for item in value.activities
            ))
            self.state.setCurrentIndex(max(0, self.state.findData(value.state)))
            self.city.setText(value.city); self.state_registration.setText(value.state_registration)
            self.municipal_registration.setText(value.municipal_registration)
            self.operation_types.setText(", ".join(value.operation_types))
            self.document_types.setText(", ".join(value.document_types))
            self.source.setText(value.source)
            self._set_date(self.source_date, value.source_date)
            self._set_date(self.effective_from, value.effective_from or date.today().isoformat())
        finally:
            self._loading = False
        self._invalidate_review()

    @staticmethod
    def _set_date(widget: QDateEdit, iso_value: str) -> None:
        parsed = QDate.fromString(str(iso_value), "yyyy-MM-dd")
        if parsed.isValid(): widget.setDate(parsed)

    def load_legacy_draft(self) -> None:
        try:
            draft = self.service.prepare_legacy_migration()
        except Exception as error:
            self._notifier("error", str(error)); return
        self._populate(draft)
        self._notifier(
            "info", "Configuração antiga carregada somente como rascunho. "
            "Ela não foi confirmada nem persistida.",
        )

    def _activities(self) -> tuple[CompanyActivity, ...]:
        result = []
        for raw in self.activities.toPlainText().splitlines():
            if not raw.strip(): continue
            parts = [part.strip() for part in raw.split("|")]
            result.append(CompanyActivity(
                parts[0], parts[1] if len(parts) > 1 else "",
                any(part.upper() == "PRINCIPAL" for part in parts[2:]),
            ))
        return tuple(result)

    @staticmethod
    def _tokens(text: str) -> tuple[str, ...]:
        return tuple(part.strip() for part in text.replace(";", ",").split(",") if part.strip())

    def _draft(self) -> CompanyProfileDraft:
        return CompanyProfileDraft(
            cnpj=self.cnpj.text(), legal_name=self.legal_name.text(),
            tax_regime=self.tax_regime.currentData(),
            business_classification=self.classification.currentData(),
            activities=self._activities(), state=self.state.currentData(), city=self.city.text(),
            state_registration=self.state_registration.text(),
            municipal_registration=self.municipal_registration.text(),
            operation_types=self._tokens(self.operation_types.text()),
            document_types=self._tokens(self.document_types.text()),
            effective_from=self.effective_from.date().toString("yyyy-MM-dd"),
            source=self.source.text(), source_date=self.source_date.date().toString("yyyy-MM-dd"),
            confirmed=False,
        )

    def review(self) -> bool:
        try:
            reviewed = self.service.prepare_review(self._draft())
            if len(self.change_reason.text().strip()) < 10:
                raise ValueError("Informe o motivo da confirmação ou mudança com ao menos 10 caracteres.")
        except Exception as error:
            self._notifier("error", str(error)); return False
        self._reviewed = reviewed
        self.review_summary.setPlainText(self._summary(reviewed))
        self.review_ack.setChecked(False)
        self.review_panel.setVisible(True); self.form_page.setEnabled(False)
        self.legacy_button.setEnabled(False); self.review_button.setEnabled(False)
        self.review_ack.setFocus(Qt.FocusReason.OtherFocusReason)
        self._sync_confirmation()
        return True

    @staticmethod
    def _summary(draft: CompanyProfileDraft) -> str:
        cnaes = ", ".join(item.cnae + (" (principal)" if item.primary else "") for item in draft.activities) or "não informado"
        return "\n".join((
            f"CNPJ: {draft.cnpj}", f"Razão social: {draft.legal_name}",
            f"Regime / enquadramento: {draft.tax_regime} / {draft.business_classification}",
            f"Localidade: {draft.city}/{draft.state}", f"IE / IM: {draft.state_registration or '-'} / {draft.municipal_registration or '-'}",
            f"CNAEs: {cnaes}", f"Operações: {', '.join(draft.operation_types) or 'não informado'}",
            f"Documentos: {', '.join(draft.document_types) or 'não informado'}",
            f"Fonte e data: {draft.source} · {draft.source_date}", f"Vigência: {draft.effective_from}",
            "Readiness: somente informativo · enables_fiscal=false",
        ))

    def _back_to_form(self) -> None:
        self.review_panel.setVisible(False); self.form_page.setEnabled(True)
        self.legacy_button.setEnabled(True); self.review_button.setEnabled(True)
        self._reviewed = None; self.review_ack.setChecked(False); self.confirm_button.setEnabled(False)
        self.cnpj.setFocus(Qt.FocusReason.OtherFocusReason)

    def _invalidate_review(self, *_args) -> None:
        if self._loading: return
        self._reviewed = None; self.review_ack.setChecked(False); self.confirm_button.setEnabled(False)

    def _sync_confirmation(self, *_args) -> None:
        self.confirm_button.setEnabled(self._reviewed is not None and self.review_ack.isChecked())

    def confirm(self) -> bool:
        if self._confirming:
            return False
        if self._reviewed is None or not self.review_ack.isChecked():
            self._notifier("error", "Revise os dados e marque a confirmação antes de salvar.")
            return False
        self._confirming = True
        self.confirm_button.setEnabled(False)
        try:
            version = self.service.confirm(
                replace(self._reviewed, confirmed=True),
                change_reason=self.change_reason.text(),
                expected_current_version=self._baseline_version,
            )
        except RuntimeError as error:
            self._notifier("error", str(error))
            self._back_to_form()
            return False
        except Exception as error:
            self._notifier("error", str(error))
            self._sync_confirmation()
            return False
        finally:
            self._confirming = False
        self._baseline_version = version.version
        self._notifier("info", f"Perfil empresarial versão {version.version} confirmado com auditoria.")
        self.accept(); return True

    def _visible_navigation(self):
        return [item for item in self._navigation if item.isVisible() and item.isEnabled()]

    def eventFilter(self, watched, event) -> bool:
        if watched in self._navigation and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                event.accept()
                if not event.isAutoRepeat(): self.reject()
                return True
            if event.key() not in {Qt.Key.Key_Return, Qt.Key.Key_Enter}: return False
            event.accept()
            if event.isAutoRepeat(): return True
            flow = self._visible_navigation()
            if watched not in flow: return True
            index = flow.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                flow[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.legacy_button: self.load_legacy_draft()
            elif watched is self.review_button: self.review()
            elif watched is self.review_ack: self.review_ack.setChecked(not self.review_ack.isChecked())
            elif watched is self.back_button: self._back_to_form()
            elif watched is self.confirm_button: self.confirm()
            elif watched is self.close_button: self.reject()
            else: flow[min(index + 1, len(flow) - 1)].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return super().eventFilter(watched, event)
