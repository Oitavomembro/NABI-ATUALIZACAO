from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from commercial.domain.cart import CartItem
from .widgets.money_edit import MoneyEdit
from .pdv_button_style import PDV_BUTTON_STYLE


class CartItemDialog(QDialog):
    """Edita somente a linha da venda; nunca altera o cadastro do produto."""

    def __init__(self, item: CartItem, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self.setWindowTitle("Editar item da venda")
        self.setModal(True)
        self.resize(470, 330)
        self.setStyleSheet(PDV_BUTTON_STYLE)
        root = QVBoxLayout(self)
        title = QLabel("EDITAR ITEM DA VENDA")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(title)
        root.addWidget(QLabel(item.description))
        explanation = QLabel(
            "As alterações valem somente para esta venda e não modificam o cadastro do produto."
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        form = QFormLayout()
        self.quantity = QLineEdit(str(item.quantity).replace(".", ","))
        self.price = MoneyEdit()
        self.price.set_value(item.unit_price)
        self.price.setEnabled(item.is_loose)
        self.discount = MoneyEdit()
        self.discount.set_value(item.discount_percent)
        form.addRow("Quantidade", self.quantity)
        form.addRow("Preço unitário", self.price)
        form.addRow("Desconto (%)", self.discount)
        root.addLayout(form)
        if not item.is_loose:
            note = QLabel("Preço do produto cadastrado preservado: falta autorização comercial específica.")
            note.setWordWrap(True)
            root.addWidget(note)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Aplicar ao item")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self._operational_widgets = tuple(
            widget for widget in (
                self.quantity, self.price, self.discount,
                self.apply_button, self.cancel_button,
            ) if widget.isEnabled()
        )
        for widget in self._operational_widgets:
            widget.installEventFilter(self)
        self.quantity.setFocus(Qt.FocusReason.OtherFocusReason)
        self.quantity.selectAll()

    def eventFilter(self, watched, event) -> bool:
        if (
            watched in self._operational_widgets
            and event.type() == QEvent.Type.KeyPress
            and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
        ):
            if event.isAutoRepeat():
                event.accept()
                return True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.focusPreviousChild()
            elif watched is self.quantity:
                (self.price if self.price.isEnabled() else self.discount).setFocus(
                    Qt.FocusReason.ShortcutFocusReason
                )
            elif watched is self.price:
                self.discount.setFocus(Qt.FocusReason.ShortcutFocusReason)
            elif watched is self.discount:
                self.apply_button.setFocus(Qt.FocusReason.ShortcutFocusReason)
            else:
                watched.click()
            event.accept()
            return True
        return super().eventFilter(watched, event)
