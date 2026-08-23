from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.customer_dto import CustomerReceiptCommand
from ui_qt.commercial.customer_dialog import STYLE, _money
from ui_qt.commercial.widgets.money_edit import MoneyEdit


class CustomerReceiptProofDialog(QDialog):
    def __init__(self, output, movement_id: int, balance_before, balance_after, parent=None):
        super().__init__(parent)
        self.output = output; self.movement_id = int(movement_id)
        self.balance_before = balance_before; self.balance_after = balance_after
        self.setWindowTitle("Recibo de pagamento")
        self.resize(720, 650); self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        title = QLabel("PAGAMENTO REGISTRADO")
        title.setStyleSheet("font-size:22px;font-weight:900;color:#00ff88")
        layout.addWidget(title)
        preview = QTextEdit(); preview.setReadOnly(True)
        preview.setStyleSheet("font-family:Consolas;font-size:14px")
        preview.setPlainText(output.preview_text(
            self.movement_id, balance_before=balance_before, balance_after=balance_after
        ))
        layout.addWidget(preview, 1)
        buttons = QHBoxLayout()
        print_button = QPushButton("Imprimir recibo")
        pdf_button = QPushButton("Salvar PDF")
        close = QPushButton("Fechar")
        print_button.clicked.connect(self._print)
        pdf_button.clicked.connect(self._pdf)
        close.clicked.connect(self.accept)
        buttons.addWidget(print_button); buttons.addWidget(pdf_button)
        buttons.addStretch(); buttons.addWidget(close); layout.addLayout(buttons)

    def _print(self) -> None:
        try:
            printer = self.output.print_receipt(
                self.movement_id, balance_before=self.balance_before,
                balance_after=self.balance_after,
            )
        except Exception as error:
            QMessageBox.critical(self, "Impressão", str(error)); return
        QMessageBox.information(self, "Impressão", f"Recibo enviado para:\n{printer}")

    def _pdf(self) -> None:
        destination, _ = QFileDialog.getSaveFileName(
            self, "Salvar recibo em PDF", f"recibo_pagamento_{self.movement_id}.pdf",
            "Arquivo PDF (*.pdf)",
        )
        if not destination:
            return
        try:
            path = self.output.generate_pdf(
                self.movement_id, destination,
                balance_before=self.balance_before, balance_after=self.balance_after,
            )
        except Exception as error:
            QMessageBox.critical(self, "PDF", str(error)); return
        QMessageBox.information(self, "PDF", f"PDF salvo em:\n{path}")


class CustomerReceiptDialog(QDialog):
    """Recebimento por ID real, com revisao humana antes da unica gravacao."""

    METHODS = ("DINHEIRO", "PIX", "DEBITO", "CREDITO", "OUTROS")

    def __init__(
        self, customer_service, actions, requested_by: str, parent=None, *, receipt_output=None
    ) -> None:
        super().__init__(parent)
        self.customer_service = customer_service
        self.actions = actions
        self.requested_by = requested_by
        self.receipt_output = receipt_output
        self._customers = ()
        self.last_result = None
        self._reviewed_command = None
        self._reviewed_balance_before = None
        self._saving = False
        self.setWindowTitle("Recebimento de cliente")
        self.setMinimumWidth(650)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        title = QLabel("RECEBIMENTO NO FICHARIO")
        title.setStyleSheet("font-size:22px;font-weight:800;color:#00d084")
        layout.addWidget(title)
        form = QFormLayout()
        self.customer = QComboBox()
        self.customer.setEditable(True)
        self.customer.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.customer.lineEdit().setPlaceholderText("Digite a ficha ou o nome")
        self.amount = MoneyEdit()
        self.method = QComboBox(); self.method.addItems(self.METHODS)
        self.payment_date = QDateEdit(QDate.currentDate())
        self.payment_date.setCalendarPopup(True)
        self.notes = QLineEdit()
        form.addRow("Cliente*", self.customer)
        form.addRow("Valor recebido*", self.amount)
        form.addRow("Forma*", self.method)
        form.addRow("Data*", self.payment_date)
        form.addRow("Observacao", self.notes)
        layout.addLayout(form)
        self.balance = QLabel("Saldo atual: R$ 0,00")
        self.balance.setStyleSheet("font-size:18px;font-weight:800")
        layout.addWidget(self.balance)
        self.review_summary = QLabel()
        self.review_summary.setWordWrap(True)
        self.review_summary.setStyleSheet(
            "background:#161b22;border:1px solid #00d084;border-radius:8px;"
            "padding:12px;font-size:16px;font-weight:700"
        )
        self.review_summary.hide(); layout.addWidget(self.review_summary)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("Cancelar  [Esc]")
        self.review_button = QPushButton("Revisar recebimento  [Enter]")
        self.review_button.setObjectName("primary")
        self.confirm = QPushButton("CONFIRMAR RECEBIMENTO  [Enter]")
        self.confirm.setObjectName("primary"); self.confirm.hide()
        cancel.clicked.connect(self.reject)
        self.review_button.clicked.connect(self._review)
        self.confirm.clicked.connect(self._confirm)
        buttons.addWidget(cancel); buttons.addWidget(self.review_button)
        buttons.addWidget(self.confirm); layout.addLayout(buttons)
        self._fields = (
            self.customer, self.amount, self.method, self.payment_date,
            self.notes, self.review_button, self.confirm,
        )
        for widget in self._fields: widget.installEventFilter(self)
        self.customer.currentIndexChanged.connect(self._refresh_balance)
        self.customer.currentIndexChanged.connect(self._invalidate_review)
        self.amount.textChanged.connect(self._invalidate_review)
        self.method.currentIndexChanged.connect(self._invalidate_review)
        self.payment_date.dateChanged.connect(self._invalidate_review)
        self.notes.textChanged.connect(self._invalidate_review)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True); self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._search_customers)
        self.customer.lineEdit().textEdited.connect(lambda _text: self._search_timer.start())
        self._load_customers()
        self.customer.setFocus(Qt.FocusReason.OtherFocusReason)

    def _load_customers(self, term: str = "") -> None:
        self._customers = self.customer_service.list_customers(term, limit=100)
        self.customer.blockSignals(True)
        self.customer.clear()
        for item in self._customers:
            label = f"Ficha {item.record_number or '-'} - {item.name}"
            self.customer.addItem(label, item.customer_id)
        self.customer.blockSignals(False)
        self._refresh_balance()

    def _search_customers(self) -> None:
        term = self.customer.currentText().strip()
        self._load_customers(term)
        if self.customer.count():
            self.customer.showPopup()

    def _refresh_balance(self) -> None:
        customer_id = self.customer.currentData()
        if customer_id is None:
            self.balance.setText("Saldo atual: R$ 0,00"); return
        details = next(
            (item for item in self._customers if item.customer_id == int(customer_id)), None
        )
        if details is None:
            details = self.customer_service.get_customer(int(customer_id))
        self.balance.setText(f"Saldo atual: {_money(details.debt_balance)}")

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {
            Qt.Key.Key_Return, Qt.Key.Key_Enter,
        }:
            if event.isAutoRepeat(): event.accept(); return True
            fields = tuple(
                field for field in self._fields
                if field is watched or (not field.isHidden() and field.isEnabled())
            )
            index = fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                fields[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.confirm:
                self._confirm()
            elif watched is self.review_button:
                self._review()
            else:
                fields[min(index + 1, len(fields) - 1)].setFocus(
                    Qt.FocusReason.TabFocusReason
                )
            event.accept(); return True
        return super().eventFilter(watched, event)

    def _command(self) -> CustomerReceiptCommand:
        customer_id = self.customer.currentData()
        if customer_id is None:
            raise ValueError("Selecione um cliente cadastrado.")
        selected_date = self.payment_date.date()
        return CustomerReceiptCommand(
            customer_id=int(customer_id), amount=self.amount.value(),
            payment_method=self.method.currentText(),
            payment_date=date(selected_date.year(), selected_date.month(), selected_date.day()),
            notes=self.notes.text(),
        )

    def _review(self) -> None:
        try:
            command = self._command()
            customer = self.customer_service.get_customer(command.customer_id)
        except Exception as error:
            QMessageBox.warning(self, "Recebimento", str(error))
            self.amount.setFocus(Qt.FocusReason.OtherFocusReason); return
        resulting_balance = max(customer.debt_balance - command.amount, type(command.amount)("0"))
        self._reviewed_command = command
        self._reviewed_balance_before = customer.debt_balance
        self.review_summary.setText(
            f"REVISÃO — NENHUM DADO SALVO\n"
            f"Ficha: {customer.record_number or '—'}   •   Cliente: {customer.name}\n"
            f"Valor: {_money(command.amount)}   •   Forma: {command.payment_method}\n"
            f"Data: {command.payment_date:%d/%m/%Y}\n"
            f"Saldo antes do pagamento: {_money(customer.debt_balance)}   •   "
            f"Saldo após confirmar: {_money(resulting_balance)}"
        )
        self.review_summary.show(); self.confirm.show(); self.review_button.setEnabled(False)
        self.confirm.setFocus(Qt.FocusReason.OtherFocusReason)

    def _invalidate_review(self, *_args) -> None:
        self._reviewed_command = None
        self._reviewed_balance_before = None
        self.review_summary.hide(); self.confirm.hide(); self.review_button.setEnabled(True)

    def _confirm(self) -> None:
        if self._reviewed_command is None or self._saving:
            return
        try:
            current_command = self._command()
        except Exception as error:
            self._invalidate_review()
            QMessageBox.warning(self, "Recebimento", str(error)); return
        if current_command != self._reviewed_command:
            self._invalidate_review()
            QMessageBox.warning(
                self, "Recebimento", "Os dados mudaram. Revise novamente antes de confirmar."
            )
            return
        command = self._reviewed_command
        balance_before = self._reviewed_balance_before
        self._saving = True; self.confirm.setEnabled(False)
        result = self.actions.receive_customer_payment(
            command,
            context=ActionContext(self.requested_by, ActionOrigin.UI),
            confirmation_granted=True,
        )
        self.last_result = result
        if not result.committed:
            QMessageBox.warning(self, "Recebimento", result.message)
            self._saving = False; self._invalidate_review()
            self.amount.setFocus(Qt.FocusReason.OtherFocusReason); return
        current = self.customer_service.get_customer(command.customer_id)
        if self.receipt_output is not None:
            CustomerReceiptProofDialog(
                self.receipt_output, result.resource_id,
                balance_before, current.debt_balance, self,
            ).exec()
        else:
            QMessageBox.information(
                self, "Comprovante de recebimento",
                f"RECEBIMENTO #{result.resource_id}\nCliente: {current.name}\n"
                f"Valor: {_money(command.amount)}\nForma: {command.payment_method}\n"
                f"Novo saldo: {_money(current.debt_balance)}",
            )
        self.accept()
