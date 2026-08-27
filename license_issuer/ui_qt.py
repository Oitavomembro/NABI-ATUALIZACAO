from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFileDialog, QFormLayout,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QPlainTextEdit, QInputDialog, QVBoxLayout, QWidget,
)

from licensing.models import LicenseEdition
from licensing.machine import machine_code, machine_fingerprint as current_machine_fingerprint

from .workflow import (
    IssuanceRequest, IssuanceReview, parse_machine_request, request_from_existing,
    load_public_catalog, review_request, sign_review, verify_license_file,
)
from .products import PRODUCTS, product


class LicenseIssuerWindow(QDialog):
    """Ferramenta administrativa externa; nunca é importada pelo NabiCode."""

    def __init__(self, parent=None, *, key_directory: Path | None = None,
                 output_directory: Path | None = None) -> None:
        super().__init__(parent)
        self._review: IssuanceReview | None = None
        self._source_license: Path | None = None
        self._source_catalog: Path | None = None
        self._key_directory = Path(key_directory) if key_directory else (
            Path.home() / "Documents" / "NabiCode-Segredos" / "licenciamento"
        )
        self._output_directory = Path(output_directory) if output_directory else (
            Path.home() / "Documents" / "NabiCode-Licencas"
        )
        self._suggested_output = ""
        self._active_product_id: str | None = None
        self.setWindowTitle("NabiCode — Emissor externo de Licenças V2")
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setMinimumSize(860, 680)
        self.resize(980, 760)

        layout = QVBoxLayout(self)
        title = QLabel("EMISSOR EXTERNO DE LICENÇAS NABICODE V2")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #00a86b;")
        warning = QLabel(
            "A chave privada permanece fora do NabiCode e só é aberta em memória no momento da assinatura."
        )
        warning.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(warning)

        form = QFormLayout()
        self.private_key = QLineEdit()
        self.private_key.setPlaceholderText("Caminho externo da chave privada criptografada")
        self.public_catalog = QLineEdit()
        self.public_catalog.setPlaceholderText("Catálogo público correspondente à chave privada")
        self.key_id = QLineEdit()
        self.machine_fingerprint = QLineEdit()
        self.machine_code = QLabel("—")
        self.customer = QLineEdit()
        self.product = QComboBox()
        for item in PRODUCTS:
            self.product.addItem(item.label, item.product_id)
        self.edition = QComboBox()
        self.duration = QComboBox()
        for months in (1, 3, 6, 9, 12):
            self.duration.addItem(f"{months} {'mês' if months == 1 else 'meses'}", months)
        self.duration.setCurrentIndex(self.duration.findData(12))
        self.valid_until = QDateEdit(QDate.currentDate().addMonths(12))
        self.valid_until.setReadOnly(True)
        self.valid_until.setButtonSymbols(QDateEdit.ButtonSymbols.NoButtons)
        self.valid_until.setDisplayFormat("dd/MM/yyyy")
        self.features = QLineEdit()
        self.features.setReadOnly(True)
        self.fiscal_enabled = QCheckBox(
            "Habilitar Fiscal/SEFAZ (somente após homologação e configuração)"
        )
        self.fiscal_enabled.setToolTip(
            "Assina apenas o direito de configurar/testar o módulo fiscal. "
            "Não libera produção nem ignora os portões fiscais do NabiCode."
        )
        self.license_id = QLineEdit()
        self.license_id.setPlaceholderText("Gerado automaticamente em nova licença")
        self.revoked = QCheckBox("Emitir revogação assinada")
        self.output = QLineEdit()
        self.output.setPlaceholderText("Arquivo de saída .nabilic")

        request_row = QHBoxLayout()
        request_row.addWidget(self.machine_code, 1)
        load_request = QPushButton("Carregar solicitação")
        load_request.clicked.connect(self._load_machine_request)
        self.local_machine_button = QPushButton("Usar esta máquina")
        self.local_machine_button.clicked.connect(self._use_current_machine)
        request_row.addWidget(load_request)
        request_row.addWidget(self.local_machine_button)
        output_row = self._path_row(self.output, self._choose_output, "Escolher saída")
        form.addRow("Produto:", self.product)
        form.addRow("Máquina:", request_row)
        form.addRow("Cliente/titular:", self.customer)
        form.addRow("Edição:", self.edition)
        form.addRow("Período:", self.duration)
        form.addRow("Validade calculada:", self.valid_until)
        form.addRow("Módulo Fiscal:", self.fiscal_enabled)
        form.addRow("Arquivo portátil:", output_row)
        layout.addLayout(form)

        self.advanced_button = QPushButton("Mostrar opções avançadas")
        self.advanced_button.setCheckable(True)
        layout.addWidget(self.advanced_button)
        self.advanced_panel = QWidget()
        advanced = QFormLayout(self.advanced_panel)
        key_row = self._path_row(self.private_key, self._choose_private_key, "Escolher chave")
        catalog_row = self._path_row(self.public_catalog, self._choose_public_catalog, "Escolher catálogo")
        advanced.addRow("Chave privada:", key_row)
        advanced.addRow("Catálogo público:", catalog_row)
        advanced.addRow("Identificador da chave:", self.key_id)
        advanced.addRow("Fingerprint técnico:", self.machine_fingerprint)
        advanced.addRow("Recursos automáticos:", self.features)
        advanced.addRow("ID da licença:", self.license_id)
        advanced.addRow("Revogação:", self.revoked)
        auxiliary = QHBoxLayout()
        self.load_existing_button = QPushButton("Carregar licença para renovar/revogar")
        self.verify_button = QPushButton("Verificar licença com chave pública")
        auxiliary.addWidget(self.load_existing_button)
        auxiliary.addWidget(self.verify_button)
        advanced.addRow(auxiliary)
        self.advanced_panel.setVisible(False)
        layout.addWidget(self.advanced_panel)

        self.review_text = QPlainTextEdit()
        self.review_text.setReadOnly(True)
        self.review_text.setPlaceholderText("A revisão imutável aparecerá aqui antes da assinatura.")
        layout.addWidget(self.review_text, 1)

        actions = QHBoxLayout()
        self.review_button = QPushButton("1. Revisar")
        self.sign_button = QPushButton("2. Assinar e gerar .nabilic")
        self.sign_button.setEnabled(False)
        self.minimize_button = QPushButton("Minimizar")
        self.close_button = QPushButton("Fechar")
        actions.addStretch()
        actions.addWidget(self.review_button)
        actions.addWidget(self.sign_button)
        actions.addWidget(self.minimize_button)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

        self.review_button.clicked.connect(self._review_request)
        self.sign_button.clicked.connect(self._sign)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.close_button.clicked.connect(self.reject)
        self.load_existing_button.clicked.connect(self._load_existing)
        self.verify_button.clicked.connect(self._verify_existing)
        self.advanced_button.toggled.connect(self._toggle_advanced)
        for widget in (
            self.private_key, self.public_catalog, self.key_id, self.machine_fingerprint, self.customer,
            self.product, self.edition, self.valid_until, self.features, self.license_id,
            self.fiscal_enabled, self.revoked, self.output,
        ):
            signal = getattr(widget, "textChanged", None)
            if signal is None:
                signal = getattr(widget, "currentTextChanged", None)
            if signal is None:
                signal = getattr(widget, "dateChanged", None)
            if signal is None:
                signal = getattr(widget, "toggled", None)
            signal.connect(self._invalidate_review)
        self.edition.currentTextChanged.connect(self._apply_edition_defaults)
        self.product.currentIndexChanged.connect(self._apply_product_defaults)
        self.fiscal_enabled.toggled.connect(self._refresh_features)
        self.duration.currentIndexChanged.connect(self._apply_duration)
        self.customer.textChanged.connect(self._suggest_output)
        self._discover_owner_keys()
        self._apply_product_defaults()
        self._apply_duration()

    def _toggle_advanced(self, visible: bool) -> None:
        self.advanced_panel.setVisible(visible)
        self.advanced_button.setText(
            "Ocultar opções avançadas" if visible else "Mostrar opções avançadas"
        )

    def _discover_owner_keys(self) -> None:
        """Descobre somente caminhos e chave pública; senha nunca é persistida."""
        catalog = self._key_directory / "trusted_public_keys.json"
        private_candidates = sorted(self._key_directory.glob("*-private.pem"))
        if not catalog.is_file() or len(private_candidates) != 1:
            return
        try:
            key_ids = tuple(load_public_catalog(catalog))
        except ValueError:
            return
        if len(key_ids) != 1:
            return
        self.private_key.setText(str(private_candidates[0]))
        self.public_catalog.setText(str(catalog))
        self.key_id.setText(key_ids[0])

    def _apply_product_defaults(self, *_args) -> None:
        selected = product(self.product.currentData())
        if self._active_product_id is not None and self._active_product_id != selected.product_id:
            self.private_key.clear()
            self.public_catalog.clear()
            self.key_id.clear()
        self._active_product_id = selected.product_id
        self.machine_fingerprint.setPlaceholderText(
            "Código NABI2 completo" if selected.product_id == "NOTAS_IGLBALT"
            else "Fingerprint técnico de 64 caracteres"
        )
        self.edition.blockSignals(True)
        self.edition.clear()
        self.edition.addItems([item.value for item in selected.editions])
        self.edition.setCurrentText(selected.default_edition.value)
        self.edition.blockSignals(False)
        self._apply_edition_defaults()

    def _apply_edition_defaults(self, *_args) -> None:
        edition = LicenseEdition(self.edition.currentText())
        commercial = self.product.currentData() == "NABICODE" and edition is LicenseEdition.COMMERCIAL
        self.fiscal_enabled.setEnabled(commercial)
        if not commercial:
            self.fiscal_enabled.setChecked(False)
        self._refresh_features()
        evaluation = edition is LicenseEdition.EVALUATION
        self.duration.setEnabled(not evaluation)
        if evaluation:
            self.duration.setCurrentIndex(self.duration.findData(1))
            self.valid_until.setDate(QDate.currentDate().addDays(29))
        self._suggest_output()

    def _refresh_features(self, *_args) -> None:
        edition = LicenseEdition(self.edition.currentText())
        selected = product(self.product.currentData())
        features = list(selected.features[edition])
        if selected.product_id == "NABICODE" and edition is LicenseEdition.COMMERCIAL and self.fiscal_enabled.isChecked():
            features.append("fiscal")
        self.features.setText(",".join(sorted(set(features))))

    def _apply_duration(self, *_args) -> None:
        if LicenseEdition(self.edition.currentText()) is LicenseEdition.EVALUATION:
            self.valid_until.setDate(QDate.currentDate().addDays(29))
            self._suggest_output()
            return
        months = int(self.duration.currentData() or 12)
        self.valid_until.setDate(QDate.currentDate().addMonths(months))
        self._suggest_output()

    def _use_current_machine(self) -> None:
        try:
            fingerprint = current_machine_fingerprint()
        except Exception as error:
            QMessageBox.critical(self, "Máquina indisponível", str(error))
            return
        code = machine_code(fingerprint)
        self.machine_fingerprint.setText(
            code if self.product.currentData() == "NOTAS_IGLBALT" else fingerprint
        )
        self.machine_code.setText(code)

    @staticmethod
    def _safe_name(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-") or "cliente"

    def _suggest_output(self, *_args) -> None:
        if self.output.text() and self.output.text() != self._suggested_output:
            return
        edition = self.edition.currentText().casefold() or "licenca"
        product_name = self._safe_name(self.product.currentText())
        customer = self._safe_name(self.customer.text())
        date_text = self.valid_until.date().toString("yyyyMMdd")
        candidate = self._output_directory / f"{product_name}-{edition}-{customer}-{date_text}.nabilic"
        sequence = 1
        while candidate.exists():
            candidate = self._output_directory / f"{product_name}-{edition}-{customer}-{date_text}-{sequence}.nabilic"
            sequence += 1
        self._suggested_output = str(candidate)
        self.output.setText(self._suggested_output)

    @staticmethod
    def _path_row(field: QLineEdit, callback, label: str):
        container = QGridLayout()
        button = QPushButton(label)
        button.clicked.connect(callback)
        container.addWidget(field, 0, 0)
        container.addWidget(button, 0, 1)
        return container

    def _invalidate_review(self, *_args) -> None:
        self._review = None
        self.sign_button.setEnabled(False)
        if self.review_text.toPlainText():
            self.review_text.setPlainText("Dados alterados. Clique em Revisar novamente.")

    def _choose_private_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Escolher chave privada", "", "PEM (*.pem);;Todos (*)")
        if path:
            self.private_key.setText(path)

    def _choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Salvar licença", "", "Licença NabiCode (*.nabilic)")
        if path:
            self.output.setText(path if path.lower().endswith(".nabilic") else path + ".nabilic")

    def _choose_public_catalog(self) -> None:
        path = self._catalog_path()
        if path is not None:
            self.public_catalog.setText(str(path))

    def _load_machine_request(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Solicitação da máquina", "", "JSON (*.json);;Todos (*)")
        if not path:
            return
        try:
            fingerprint, code = parse_machine_request(Path(path).read_bytes())
        except Exception as error:
            QMessageBox.critical(self, "Solicitação inválida", str(error))
            return
        self.machine_fingerprint.setText(fingerprint)
        self.machine_code.setText(code)

    def _catalog_path(self) -> Path | None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Catálogo de chaves públicas", "", "JSON (*.json);;Todos (*)"
        )
        return Path(path) if path else None

    def _load_existing(self) -> None:
        license_path, _ = QFileDialog.getOpenFileName(
            self, "Licença existente", "", "Licença NabiCode (*.nabilic)"
        )
        if not license_path:
            return
        catalog = self._catalog_path()
        if catalog is None:
            return
        try:
            payload = verify_license_file(license_path, catalog)
        except Exception as error:
            QMessageBox.critical(self, "Licença inválida", str(error))
            return
        self._source_license = Path(license_path)
        self._source_catalog = catalog
        self.public_catalog.setText(str(catalog))
        self.machine_fingerprint.setText(payload.machine_fingerprint)
        self.machine_code.setText(machine_code(payload.machine_fingerprint))
        self.customer.setText(payload.customer_name)
        product_index = self.product.findData(payload.product_id)
        if product_index < 0:
            QMessageBox.critical(self, "Produto desconhecido", "O produto desta licença não é suportado.")
            return
        self.product.setCurrentIndex(product_index)
        self.edition.setCurrentText(payload.edition.value)
        self.fiscal_enabled.setChecked("fiscal" in payload.features)
        self._refresh_features()
        self.license_id.setText(payload.license_id)
        suggested = max(date.today(), payload.valid_until) + timedelta(days=365)
        self.valid_until.setDate(QDate(suggested.year, suggested.month, suggested.day))
        self.revoked.setChecked(False)
        QMessageBox.information(self, "Licença carregada", "Dados verificados. Ajuste a validade ou marque revogação e clique em Revisar.")

    def _verify_existing(self) -> None:
        license_path, _ = QFileDialog.getOpenFileName(
            self, "Verificar licença", "", "Licença NabiCode (*.nabilic)"
        )
        if not license_path:
            return
        catalog = self._catalog_path()
        if catalog is None:
            return
        try:
            payload = verify_license_file(license_path, catalog)
        except Exception as error:
            QMessageBox.critical(self, "Verificação falhou", str(error))
            return
        QMessageBox.information(
            self, "Assinatura válida",
            f"Cliente: {payload.customer_name}\nEdição: {payload.edition.value}\n"
            f"Validade: {payload.valid_until:%d/%m/%Y}\nRevogada: {'SIM' if payload.revoked else 'NÃO'}",
        )

    def _date(self) -> date:
        value = self.valid_until.date()
        return date(value.year(), value.month(), value.day())

    def _build_request(self) -> IssuanceRequest:
        issued_at = datetime.now(timezone.utc).replace(microsecond=0)
        if self._source_license is not None and self._source_catalog is not None:
            return request_from_existing(
                self._source_license, self._source_catalog,
                valid_until=self._date(), issued_at=issued_at,
                revoked=self.revoked.isChecked(),
            )
        return IssuanceRequest(
            product_id=self.product.currentData(),
            key_id=self.key_id.text(),
            machine_fingerprint=self.machine_fingerprint.text(),
            customer_name=self.customer.text(),
            edition=LicenseEdition(self.edition.currentText()),
            valid_until=self._date(),
            features=tuple(part.strip() for part in self.features.text().split(",") if part.strip()),
            license_id=self.license_id.text().strip() or None,
            revoked=self.revoked.isChecked(),
            issued_at=issued_at,
        )

    def _review_request(self) -> None:
        try:
            review = review_request(self._build_request())
        except Exception as error:
            QMessageBox.critical(self, "Dados inválidos", str(error))
            return
        self.machine_code.setText(str(review.summary["codigo_maquina"]))
        self.license_id.blockSignals(True)
        self.license_id.setText(str(review.summary["license_id"]))
        self.license_id.blockSignals(False)
        lines = ["REVISÃO — NENHUM ARQUIVO FOI ASSINADO", ""]
        lines.extend(f"{key}: {value}" for key, value in review.summary.items())
        lines.extend(("", f"Código da revisão: {review.digest}"))
        self.review_text.setPlainText("\n".join(lines))
        self._review = review
        self.sign_button.setEnabled(True)

    def _sign(self) -> None:
        if self._review is None:
            QMessageBox.warning(self, "Revisão necessária", "Revise os dados antes de assinar.")
            return
        password, accepted = QInputDialog.getText(
            self, "Senha da chave privada", "Senha:", QLineEdit.EchoMode.Password
        )
        if not accepted:
            return
        try:
            artifact = sign_review(
                self._review,
                private_key_path=self.private_key.text(),
                public_catalog_path=self.public_catalog.text(),
                password=password.encode("utf-8"),
                output_path=self.output.text(),
            )
        except Exception as error:
            QMessageBox.critical(self, "Emissão não realizada", str(error))
            return
        self.sign_button.setEnabled(False)
        QMessageBox.information(
            self, "Licença emitida",
            f"Arquivo: {artifact.path}\nSHA-256: {artifact.sha256}\n"
            "A chave privada não foi incluída no arquivo.",
        )
