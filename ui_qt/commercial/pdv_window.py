from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from commercial.domain.money import MoneyCodec

from .checkout_dialog import CheckoutDialog
from .pdv_view_model import PDVViewModel
from .widgets.money_edit import MoneyEdit


class PDVWindow(QMainWindow):
    def __init__(self, view_model: PDVViewModel) -> None:
        super().__init__()
        self.view_model = view_model
        self.setWindowTitle("NabiCode — PDV Comercial Qt")
        self.resize(1120, 760)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.addWidget(self._customer_panel())
        layout.addWidget(self._item_panel())
        layout.addWidget(self._cart_panel(), 1)
        footer = QHBoxLayout()
        self.total_label = QLabel("Total: R$ 0,00")
        self.total_label.setStyleSheet("font-size: 24px; font-weight: 700")
        self.checkout_button = QPushButton("Finalizar venda")
        self.checkout_button.clicked.connect(self._checkout)
        footer.addWidget(self.total_label)
        footer.addStretch()
        footer.addWidget(self.checkout_button)
        layout.addLayout(footer)

    def _customer_panel(self) -> QGroupBox:
        box = QGroupBox("Cliente")
        layout = QGridLayout(box)
        self.customer_search = QLineEdit()
        self.customer_search.setPlaceholderText("Ficha ou nome")
        self.customer_results = QListWidget()
        self.customer_results.setMaximumHeight(110)
        self.customer_selected = QLabel("Nenhum cliente selecionado")
        clear = QPushButton("Limpar seleção")
        self.customer_search.textChanged.connect(self._search_customers)
        self.customer_results.itemActivated.connect(self._select_customer)
        self.customer_results.itemClicked.connect(self._select_customer)
        clear.clicked.connect(self._clear_customer)
        layout.addWidget(self.customer_search, 0, 0, 1, 2)
        layout.addWidget(clear, 0, 2)
        layout.addWidget(self.customer_results, 1, 0, 1, 3)
        layout.addWidget(self.customer_selected, 2, 0, 1, 3)
        return box

    def _item_panel(self) -> QGroupBox:
        box = QGroupBox("Item")
        layout = QGridLayout(box)
        self.loose_item = QCheckBox("Produto avulso")
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("Nome, código ou código de barras")
        self.product_results = QListWidget()
        self.product_results.setMaximumHeight(100)
        self.description = QLineEdit()
        self.description.setReadOnly(True)
        self.quantity = QLineEdit("1")
        self.price = MoneyEdit()
        self.price.setReadOnly(True)
        add = QPushButton("Adicionar ao carrinho")
        self.loose_item.toggled.connect(self._toggle_loose)
        self.product_search.textChanged.connect(self._search_products)
        self.product_results.itemActivated.connect(self._select_product)
        self.product_results.itemClicked.connect(self._select_product)
        add.clicked.connect(self._add_item)
        layout.addWidget(self.loose_item, 0, 0)
        layout.addWidget(self.product_search, 0, 1, 1, 3)
        layout.addWidget(self.product_results, 1, 1, 1, 3)
        layout.addWidget(QLabel("Descrição"), 2, 0)
        layout.addWidget(self.description, 2, 1, 1, 3)
        layout.addWidget(QLabel("Quantidade"), 3, 0)
        layout.addWidget(self.quantity, 3, 1)
        layout.addWidget(QLabel("Preço"), 3, 2)
        layout.addWidget(self.price, 3, 3)
        layout.addWidget(add, 4, 3)
        return box

    def _cart_panel(self) -> QGroupBox:
        box = QGroupBox("Carrinho")
        layout = QVBoxLayout(box)
        self.cart = QTableWidget(0, 5)
        self.cart.setHorizontalHeaderLabels(
            ["Descrição", "Quantidade", "Preço unitário", "Subtotal", ""]
        )
        self.cart.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart.horizontalHeader().setStretchLastSection(False)
        self.cart.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.cart)
        return box

    def _show_error(self, error: Exception) -> None:
        QMessageBox.warning(self, "NabiCode", str(error) or "Operação não concluída.")

    def _search_customers(self, term: str) -> None:
        self.customer_results.clear()
        if not term.strip():
            return
        try:
            records = self.view_model.search_customers(term)
        except Exception as error:
            self._show_error(error)
            return
        for record in records:
            reference = record.record_number if record.record_number is not None else record.code
            item = QListWidgetItem(f"{reference} — {record.name}")
            item.setData(Qt.ItemDataRole.UserRole, record.customer_id)
            self.customer_results.addItem(item)

    def _select_customer(self, item: QListWidgetItem) -> None:
        try:
            customer = self.view_model.select_customer(int(item.data(Qt.ItemDataRole.UserRole)))
            reference = customer.record_number if customer.record_number is not None else customer.code
            self.customer_selected.setText(f"Selecionado: {reference} — {customer.name}")
            self.customer_results.clear()
        except Exception as error:
            self._show_error(error)

    def _clear_customer(self) -> None:
        self.view_model.clear_customer()
        self.customer_selected.setText("Nenhum cliente selecionado")

    def _search_products(self, term: str) -> None:
        self.product_results.clear()
        if self.loose_item.isChecked() or not term.strip():
            return
        try:
            records = self.view_model.search_products(term)
        except Exception as error:
            self._show_error(error)
            return
        for record in records:
            item = QListWidgetItem(f"{record.code} — {record.description}")
            item.setData(Qt.ItemDataRole.UserRole, record.product_id)
            self.product_results.addItem(item)

    def _select_product(self, item: QListWidgetItem) -> None:
        try:
            product = self.view_model.select_product(int(item.data(Qt.ItemDataRole.UserRole)))
            self.description.setText(product.description)
            self.price.set_value(product.unit_price)
            self.product_results.clear()
        except Exception as error:
            self._show_error(error)

    def _toggle_loose(self, enabled: bool) -> None:
        self.view_model.clear_product()
        self.product_search.clear()
        self.product_search.setEnabled(not enabled)
        self.description.setReadOnly(not enabled)
        self.price.setReadOnly(not enabled)
        self.description.clear()
        self.description.setPlaceholderText("")
        self.price.clear_value()
        if enabled:
            self.description.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.product_search.setFocus(Qt.FocusReason.OtherFocusReason)

    def _add_item(self) -> None:
        try:
            if self.loose_item.isChecked():
                self.view_model.add_loose_item(
                    self.description.text(), self.quantity.text(), self.price.value()
                )
                self.description.clear()
                self.price.clear_value()
                self.description.setFocus(Qt.FocusReason.OtherFocusReason)
            else:
                self.view_model.add_selected_product(self.quantity.text())
                self.view_model.clear_product()
                self.description.clear()
                self.price.clear_value()
                self.product_search.clear()
            self.quantity.setText("1")
            self.refresh_cart()
        except Exception as error:
            self._show_error(error)

    def refresh_cart(self) -> None:
        items = self.view_model.session.cart.items
        self.cart.setRowCount(len(items))
        for row, item in enumerate(items):
            values = (
                item.description, str(item.quantity), MoneyCodec.format_br(item.net_unit_price),
                MoneyCodec.format_br(item.subtotal),
            )
            for column, value in enumerate(values):
                self.cart.setItem(row, column, QTableWidgetItem(value))
            remove = QPushButton("Remover")
            remove.clicked.connect(lambda _checked=False, line=item.line_id: self._remove_item(line))
            self.cart.setCellWidget(row, 4, remove)
        self.total_label.setText(f"Total: R$ {MoneyCodec.format_br(self.view_model.total)}")

    def _remove_item(self, line_id: str) -> None:
        try:
            self.view_model.remove_item(line_id)
            self.refresh_cart()
        except Exception as error:
            self._show_error(error)

    def _checkout(self) -> None:
        dialog = CheckoutDialog(self.view_model.total, self)
        if dialog.exec() != CheckoutDialog.DialogCode.Accepted:
            return
        try:
            result = self.view_model.checkout(dialog.checkout_input(), user="Sistema")
        except Exception as error:
            self._show_error(error)
            return
        if result.committed:
            title = "Venda confirmada"
            message = result.message
            if result.secondary_effect_failed:
                QMessageBox.warning(self, title, message)
            else:
                QMessageBox.information(self, title, message)
            self.customer_selected.setText("Nenhum cliente selecionado")
            self.refresh_cart()
        else:
            QMessageBox.warning(self, "Venda recusada", result.message)
