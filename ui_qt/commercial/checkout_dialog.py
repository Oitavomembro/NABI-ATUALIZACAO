from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from commercial.domain.money import MoneyCodec
from commercial.domain.payments import Payment, PaymentMethod
from .pdv_view_model import CheckoutInput, PDVViewModel
from .widgets.money_edit import MoneyEdit


class CheckoutDialog(QDialog):
    METHODS = (
        ("Dinheiro", PaymentMethod.CASH), ("PIX", PaymentMethod.PIX),
        ("Débito", PaymentMethod.DEBIT), ("Crédito", PaymentMethod.CREDIT_CARD),
        ("Crediário", PaymentMethod.STORE_CREDIT), ("Outros", PaymentMethod.OTHER),
    )

    def __init__(self, view_model: PDVViewModel, parent=None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self._payments: list[Payment] = []
        self._reviewed_input: CheckoutInput | None = None
        self._confirmed_input: CheckoutInput | None = None
        self._confirming = False
        self.setWindowTitle("Pagamentos")
        self.setModal(True)
        self.resize(820, 680)
        root = QVBoxLayout(self)
        self.total_label = QLabel()
        self.total_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(self.total_label)

        form = QFormLayout()
        self.method = QComboBox()
        for label, method in self.METHODS:
            self.method.addItem(label, method)
        self.amount = MoneyEdit()
        self.amount.set_value(view_model.total)
        self.authorization = QLineEdit()
        self.authorization.setMaxLength(20)
        self.authorization.setPlaceholderText("NSU / autorização opcional")
        self.add_payment = QPushButton("Adicionar pagamento")
        form.addRow("Forma", self.method)
        form.addRow("Valor", self.amount)
        form.addRow("Autorização POS", self.authorization)
        form.addRow(self.add_payment)
        root.addLayout(form)

        self.payment_table = QTableWidget(0, 3)
        self.payment_table.setHorizontalHeaderLabels(["Forma", "Valor", "Autorização"])
        root.addWidget(self.payment_table)
        self.remove_payment = QPushButton("Remover pagamento selecionado")
        root.addWidget(self.remove_payment)

        adjustments = QHBoxLayout()
        self.discount_type = QComboBox()
        self.discount_type.addItem("Desconto em valor", "VALUE")
        self.discount_type.addItem("Desconto em %", "PERCENT")
        self.discount = MoneyEdit()
        self.surcharge_type = QComboBox()
        self.surcharge_type.addItem("Acréscimo em valor", "VALUE")
        self.surcharge_type.addItem("Acréscimo em %", "PERCENT")
        self.surcharge = MoneyEdit()
        for widget in (self.discount_type, self.discount, self.surcharge_type, self.surcharge):
            adjustments.addWidget(widget)
        root.addLayout(adjustments)

        self.credit_box = QWidget()
        credit = QFormLayout(self.credit_box)
        self.installments = QSpinBox()
        self.installments.setRange(1, 120)
        self.first_due = QDateEdit()
        self.first_due.setCalendarPopup(True)
        due = date.today() + timedelta(days=30)
        self.first_due.setDate(QDate(due.year, due.month, due.day))
        credit.addRow("Parcelas do crediário", self.installments)
        credit.addRow("Primeiro vencimento", self.first_due)
        root.addWidget(self.credit_box)

        self.balance_label = QLabel()
        self.balance_label.setStyleSheet(
            "font-size: 28px; font-weight: 800; color: #00e676; padding: 8px 0;"
        )
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #ff6b6b;")
        root.addWidget(self.balance_label)
        root.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.review_button = self.buttons.addButton(
            "Revisar", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.confirm_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.confirm_button.setText("Confirmar venda")
        self.confirm_button.setEnabled(False)
        root.addWidget(self.buttons)

        self.method.currentIndexChanged.connect(self._sync_method)
        self.add_payment.clicked.connect(self._add_payment)
        self.remove_payment.clicked.connect(self._remove_payment)
        self.review_button.clicked.connect(self._review)
        self.buttons.accepted.connect(self._confirm)
        self.buttons.rejected.connect(self.reject)
        for widget in (self.amount, self.discount, self.surcharge):
            widget.textChanged.connect(self._refresh_totals)
        for widget in (self.discount_type, self.surcharge_type):
            widget.currentIndexChanged.connect(self._refresh_totals)
        self.method.currentIndexChanged.connect(self._invalidate_review)
        self.authorization.textChanged.connect(self._invalidate_review)
        self.installments.valueChanged.connect(self._invalidate_review)
        self.first_due.dateChanged.connect(self._invalidate_review)
        for widget in (self.amount, self.discount, self.surcharge):
            widget.textChanged.connect(self._invalidate_review)
        for widget in (self.discount_type, self.surcharge_type):
            widget.currentIndexChanged.connect(self._invalidate_review)
        self._install_navigation()
        self._sync_method()
        self._refresh_totals()
        self.method.setFocus(Qt.FocusReason.OtherFocusReason)

    def _install_navigation(self) -> None:
        self._navigation = (
            self.method, self.amount, self.authorization, self.add_payment,
            self.discount_type, self.discount, self.surcharge_type, self.surcharge,
            self.installments, self.first_due,
            self.review_button, self.confirm_button,
        )
        for widget in self._navigation:
            widget.installEventFilter(self)

    def _visible_navigation(self):
        return [widget for widget in self._navigation if widget.isVisible() and widget.isEnabled()]

    def eventFilter(self, watched, event) -> bool:
        if (watched in self._navigation and event.type() == QEvent.Type.KeyPress
                and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}):
            event.accept()
            if event.isAutoRepeat():
                return True
            flow = self._visible_navigation()
            index = flow.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                flow[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.add_payment:
                self._add_payment()
            elif watched is self.review_button:
                self._review()
            elif watched is self.confirm_button:
                self._confirm()
            else:
                flow[index + 1].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return super().eventFilter(watched, event)

    def _sync_method(self) -> None:
        method = self.method.currentData()
        is_card = method in {PaymentMethod.DEBIT, PaymentMethod.CREDIT_CARD}
        if not is_card:
            self.authorization.clear()
        self.authorization.setVisible(is_card)
        self.credit_box.setVisible(method is PaymentMethod.STORE_CREDIT or any(
            payment.method is PaymentMethod.STORE_CREDIT for payment in self._payments
        ))

    def _current_payment(self) -> Payment:
        return Payment(self.method.currentData(), self.amount.value(), self.authorization.text())

    def _add_payment(self) -> bool:
        try:
            _discount, _surcharge, final = self.view_model.application.resolve_adjustments(
                self.view_model.session.items_total, **self._adjustment_data()
            )
        except ValueError as error:
            self.error_label.setText(str(error))
            return False
        paid_before = sum((payment.amount for payment in self._payments), Decimal("0"))
        if self._payments and paid_before >= final:
            self.error_label.setText("O total já está coberto. Revise os pagamentos.")
            self.discount_type.setFocus(Qt.FocusReason.OtherFocusReason)
            return False
        try:
            self._payments.append(self._current_payment())
        except ValueError as error:
            self.error_label.setText(str(error))
            self.amount.setFocus(Qt.FocusReason.OtherFocusReason)
            self.amount.selectAll()
            return False
        self.authorization.clear()
        self._invalidate_review()
        self._render_payments()
        self._refresh_totals()
        paid = sum((payment.amount for payment in self._payments), Decimal("0"))
        if paid >= final:
            self.discount_type.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.amount.set_value(final - paid)
            self.method.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def _remove_payment(self) -> None:
        row = self.payment_table.currentRow()
        if row >= 0:
            self._payments.pop(row)
            self._invalidate_review()
            self._render_payments()
            self._refresh_totals()

    def _render_payments(self) -> None:
        self.payment_table.setRowCount(len(self._payments))
        for row, payment in enumerate(self._payments):
            values = (payment.method.value, MoneyCodec.format_br(payment.amount), payment.card_authorization)
            for column, value in enumerate(values):
                self.payment_table.setItem(row, column, QTableWidgetItem(value))
        self._sync_method()

    def _adjustment_data(self):
        return {
            "discount": self.discount.value(), "discount_type": self.discount_type.currentData(),
            "surcharge": self.surcharge.value(), "surcharge_type": self.surcharge_type.currentData(),
        }

    def _candidate_input(self) -> CheckoutInput:
        payments = tuple(self._payments) or (self._current_payment(),)
        selected = self.first_due.date()
        return CheckoutInput(
            payments=payments, installment_count=self.installments.value(),
            first_due_date=date(selected.year(), selected.month(), selected.day()),
            **self._adjustment_data(),
        )

    def _refresh_totals(self) -> None:
        try:
            discount, surcharge, final = self.view_model.application.resolve_adjustments(
                self.view_model.session.items_total, **self._adjustment_data()
            )
            paid = sum((payment.amount for payment in self._payments), self.amount.value() if not self._payments else Decimal("0"))
            difference = paid - final
            self.balance_label.setText(
                f"TROCO: R$ {MoneyCodec.format_br(difference)}" if difference >= 0
                else f"FALTA: R$ {MoneyCodec.format_br(-difference)}"
            )
            self.total_label.setText(
                f"Subtotal R$ {MoneyCodec.format_br(self.view_model.session.items_total)}  •  "
                f"Desconto R$ {MoneyCodec.format_br(discount)}  •  "
                f"Acréscimo R$ {MoneyCodec.format_br(surcharge)}  •  Total R$ {MoneyCodec.format_br(final)}"
            )
            self.error_label.clear()
        except ValueError as error:
            self.error_label.setText(str(error))

    def _summary(self, preview) -> str:
        plan, validation, terms, discount, surcharge, final = preview
        customer = self.view_model.selected_customer
        items = "\n".join(
            f"• {item.quantity} × {item.description}: R$ {MoneyCodec.format_br(item.subtotal)}"
            for item in self.view_model.session.cart.items
        )
        payments = "\n".join(
            f"• {payment.method.value}: R$ {MoneyCodec.format_br(payment.amount)}"
            + (f" — autorização {payment.card_authorization}" if payment.card_authorization else "")
            for payment in plan.payments
        )
        credit = "" if terms is None else (
            f"\nCrediário: {terms.installment_count} parcela(s), primeiro vencimento "
            f"{terms.installments[0].due_date:%d/%m/%Y}"
        )
        return (
            f"Cliente: {customer.name if customer else 'Não selecionado'}\n\nItens:\n{items}\n\n"
            f"Subtotal: R$ {MoneyCodec.format_br(self.view_model.session.items_total)}\n"
            f"Desconto: R$ {MoneyCodec.format_br(discount)}\nAcréscimo: R$ {MoneyCodec.format_br(surcharge)}\n"
            f"Total final: R$ {MoneyCodec.format_br(final)}\n\nPagamentos:\n{payments}\n"
            f"Recebido: R$ {MoneyCodec.format_br(validation.received)}\n"
            f"Troco: R$ {MoneyCodec.format_br(validation.change)}{credit}"
        )

    def _invalidate_review(self, *_args) -> None:
        self._reviewed_input = None
        self._confirmed_input = None
        self.confirm_button.setEnabled(False)

    def _review(self) -> None:
        try:
            data = self._candidate_input()
            preview = self.view_model.preview_checkout(data)
        except (TypeError, ValueError) as error:
            self.error_label.setText(str(error))
            return
        self._reviewed_input = data
        self.confirm_button.setEnabled(True)
        QMessageBox.information(self, "Revisão da venda", self._summary(preview))
        self.confirm_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _confirm(self) -> None:
        if self._confirming:
            return
        if self._reviewed_input is None:
            self.error_label.setText("Revise a venda antes de confirmar.")
            self.review_button.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        try:
            current = self._candidate_input()
            if current != self._reviewed_input:
                self._invalidate_review()
                raise ValueError("Os dados mudaram. Revise a venda novamente.")
            self.view_model.preview_checkout(current)
        except (TypeError, ValueError) as error:
            self.error_label.setText(str(error))
            return
        self._confirming = True
        self.confirm_button.setEnabled(False)
        self._confirmed_input = current
        self.accept()

    def checkout_input(self) -> CheckoutInput:
        if self._confirmed_input is None:
            raise RuntimeError("A venda ainda não possui confirmação explícita.")
        return self._confirmed_input
