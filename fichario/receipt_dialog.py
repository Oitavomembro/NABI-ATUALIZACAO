from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.customer_dto import CustomerReceiptCommand
from ui_qt.commercial.customer_dialog import STYLE, _money
from ui_qt.commercial.widgets.money_edit import MoneyEdit


class CustomerReceiptDialog(QDialog):
    """Recebimento por ID real, com revisao humana antes da unica gravacao."""

    METHODS = ("DINHEIRO", "PIX", "DEBITO", "CREDITO", "OUTROS")

    def __init__(self, customer_service, actions, requested_by: str, parent=None) -> None:
        super().__init__(parent)
        self.customer_service = customer_service
        self.actions = actions
        self.requested_by = requested_by
        self._customers = ()
        self.last_result = None
        self.setWindowTitle("Recebimento de cliente")
        self.setMinimumWidth(650)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        title = QLabel("RECEBIMENTO NO FICHARIO")
        title.setStyleSheet("font-size:22px;font-weight:800;color:#00d084")
        layout.addWidget(title)
        form = QFormLayout()
        self.customer = QComboBox()
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
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("Cancelar  [Esc]")
        self.confirm = QPushButton("Revisar recebimento  [Enter]")
        self.confirm.setObjectName("primary")
        cancel.clicked.connect(self.reject); self.confirm.clicked.connect(self._review)
        buttons.addWidget(cancel); buttons.addWidget(self.confirm); layout.addLayout(buttons)
        self._fields = (
            self.customer, self.amount, self.method, self.payment_date,
            self.notes, self.confirm,
        )
        for widget in self._fields: widget.installEventFilter(self)
        self.customer.currentIndexChanged.connect(self._refresh_balance)
        self._load_customers()
        self.customer.setFocus(Qt.FocusReason.OtherFocusReason)

    def _load_customers(self) -> None:
        self._customers = self.customer_service.list_customers("", limit=500)
        self.customer.clear()
        for item in self._customers:
            label = f"Ficha {item.record_number or '-'} - {item.name}"
            self.customer.addItem(label, item.customer_id)
        self._refresh_balance()

    def _refresh_balance(self) -> None:
        customer_id = self.customer.currentData()
        if customer_id is None:
            self.balance.setText("Saldo atual: R$ 0,00"); return
        details = self.customer_service.get_customer(int(customer_id))
        self.balance.setText(f"Saldo atual: {_money(details.debt_balance)}")

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {
            Qt.Key.Key_Return, Qt.Key.Key_Enter,
        }:
            if event.isAutoRepeat(): event.accept(); return True
            index = self._fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._fields[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.confirm:
                self._review()
            else:
                self._fields[min(index + 1, len(self._fields) - 1)].setFocus(
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
        answer = QMessageBox.question(
            self, "Confirmar recebimento",
            f"Cliente: {customer.name}\nValor: {_money(command.amount)}\n"
            f"Forma: {command.payment_method}\n\nConfirmar o recebimento?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            self.confirm.setFocus(Qt.FocusReason.OtherFocusReason); return
        result = self.actions.receive_customer_payment(
            command,
            context=ActionContext(self.requested_by, ActionOrigin.UI),
            confirmation_granted=True,
        )
        self.last_result = result
        if not result.committed:
            QMessageBox.warning(self, "Recebimento", result.message)
            self.amount.setFocus(Qt.FocusReason.OtherFocusReason); return
        current = self.customer_service.get_customer(command.customer_id)
        QMessageBox.information(
            self, "Comprovante de recebimento",
            f"RECEBIMENTO #{result.resource_id}\nCliente: {current.name}\n"
            f"Valor: {_money(command.amount)}\nForma: {command.payment_method}\n"
            f"Novo saldo: {_money(current.debt_balance)}",
        )
        self.accept()
