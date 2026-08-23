from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QWidget,
)

from commercial.domain.payments import PaymentMethod

from .pdv_view_model import CheckoutInput
from .widgets.money_edit import MoneyEdit


class CheckoutDialog(QDialog):
    def __init__(self, total, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Finalizar venda")
        self.setModal(True)
        layout = QFormLayout(self)
        self.method = QComboBox()
        for label, method in (
            ("Dinheiro", PaymentMethod.CASH), ("PIX", PaymentMethod.PIX),
            ("Débito", PaymentMethod.DEBIT), ("Crédito", PaymentMethod.CREDIT_CARD),
            ("Crediário", PaymentMethod.STORE_CREDIT),
        ):
            self.method.addItem(label, method)
        self.amount = MoneyEdit()
        self.amount.set_value(total)
        self.credit_box = QWidget()
        credit_layout = QFormLayout(self.credit_box)
        self.entrance_method = QComboBox()
        for label, method in (
            ("Dinheiro", PaymentMethod.CASH), ("PIX", PaymentMethod.PIX),
            ("Débito", PaymentMethod.DEBIT), ("Crédito", PaymentMethod.CREDIT_CARD),
        ):
            self.entrance_method.addItem(label, method)
        self.entrance = MoneyEdit()
        self.installments = QSpinBox()
        self.installments.setRange(1, 120)
        self.first_due = QDateEdit()
        self.first_due.setCalendarPopup(True)
        due = date.today() + timedelta(days=30)
        self.first_due.setDate(QDate(due.year, due.month, due.day))
        credit_layout.addRow("Forma da entrada", self.entrance_method)
        credit_layout.addRow("Entrada", self.entrance)
        credit_layout.addRow("Parcelas", self.installments)
        credit_layout.addRow("Primeiro vencimento", self.first_due)
        layout.addRow("Forma", self.method)
        layout.addRow("Valor / financiado", self.amount)
        layout.addRow(self.credit_box)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.method.currentIndexChanged.connect(self._sync_method)
        self._sync_method()

    def _sync_method(self) -> None:
        self.credit_box.setVisible(self.method.currentData() is PaymentMethod.STORE_CREDIT)

    def checkout_input(self) -> CheckoutInput:
        selected = self.first_due.date()
        return CheckoutInput(
            method=self.method.currentData(),
            amount=self.amount.value(),
            entrance_method=self.entrance_method.currentData(),
            entrance_amount=self.entrance.value(),
            installment_count=self.installments.value(),
            first_due_date=date(selected.year(), selected.month(), selected.day()),
        )
