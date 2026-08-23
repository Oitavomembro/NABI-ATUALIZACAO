from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from commercial.domain.money import MoneyCodec

from .checkout_dialog import CheckoutDialog
from .pdv_view_model import PDVViewModel
from .widgets.money_edit import MoneyEdit


class PDVWindow(QMainWindow):
    COLORS = {
        "background": "#0d1117", "panel": "#161b22", "field": "#0d1117",
        "border": "#30363d", "text": "#f0f6fc", "muted": "#8b949e",
        "green": "#2ea043", "green_hover": "#238636", "nabi": "#00d084",
        "blue": "#1f6feb", "blue_hover": "#1158c7", "red": "#da3633",
    }

    def __init__(
        self,
        view_model: PDVViewModel,
        *,
        cash_label: str = "Caixa ativo",
        profile_label: str = "COMERCIAL / NÃO FISCAL",
    ) -> None:
        super().__init__()
        self.view_model = view_model
        self.setWindowTitle("NabiCode — NABI VENDAS")
        self.setMinimumSize(960, 620)
        self.resize(1280, 760)
        self.setStyleSheet(self._style_sheet())
        root = QWidget()
        root.setObjectName("pdvRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header(cash_label, profile_label))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 12, 14, 10)
        content_layout.setSpacing(8)
        content_layout.addWidget(self._top_bar())
        content_layout.addWidget(self._operation_panel())
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._cart_panel())
        splitter.addWidget(self._summary_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 300])
        content_layout.addWidget(splitter, 1)
        layout.addWidget(content, 1)
        layout.addWidget(self._footer())
        self._install_shortcuts()

    @classmethod
    def _style_sheet(cls) -> str:
        c = cls.COLORS
        return f"""
            #pdvRoot {{ background: {c['background']}; color: {c['text']}; }}
            QFrame#header, QFrame#footer {{ background: {c['panel']}; border: 0; }}
            QFrame#panel {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 10px; }}
            QLabel {{ color: {c['text']}; }}
            QLabel#muted {{ color: {c['muted']}; }}
            QLabel#sectionTitle {{ font-size: 14px; font-weight: 700; }}
            QLabel#brand {{ color: {c['nabi']}; font-size: 24px; font-weight: 800; }}
            QLabel#total {{ color: #00ff88; font-size: 28px; font-weight: 800; }}
            QLineEdit, QListWidget, QTableWidget {{
                background: {c['field']}; color: {c['text']}; border: 1px solid {c['border']};
                border-radius: 6px; selection-background-color: {c['blue']};
            }}
            QLineEdit {{ min-height: 38px; padding: 0 10px; font-size: 14px; }}
            QListWidget {{ padding: 3px; }}
            QTableWidget {{ gridline-color: {c['border']}; border-radius: 6px; }}
            QHeaderView::section {{
                background: #21262d; color: {c['text']}; border: 0; border-right: 1px solid {c['border']};
                border-bottom: 1px solid {c['border']}; padding: 9px; font-weight: 700;
            }}
            QPushButton {{
                background: #30363d; color: {c['text']}; border: 0; border-radius: 6px;
                min-height: 36px; padding: 0 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #484f58; }}
            QPushButton#primary {{ background: {c['blue']}; }}
            QPushButton#primary:hover {{ background: {c['blue_hover']}; }}
            QPushButton#checkout {{ background: {c['green']}; min-height: 50px; font-size: 15px; }}
            QPushButton#checkout:hover {{ background: {c['green_hover']}; }}
            QPushButton#close {{ background: {c['red']}; }}
            QPushButton#inactive {{ color: #c9d1d9; background: #30363d; }}
            QCheckBox {{ color: {c['text']}; font-weight: 700; spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; }}
            QSplitter::handle {{ background: {c['background']}; width: 8px; }}
        """

    def _header(self, cash_label: str, profile_label: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("header")
        frame.setFixedHeight(64)
        row = QHBoxLayout(frame)
        row.setContentsMargins(22, 10, 18, 10)
        brand = QLabel("▰  NABI VENDAS")
        brand.setObjectName("brand")
        status = QLabel(f"{cash_label}  •  {profile_label}")
        status.setObjectName("muted")
        status.setStyleSheet("font-size: 13px; font-weight: 700;")
        close = QPushButton("Fechar  [Esc]")
        close.setObjectName("close")
        close.setMinimumWidth(120)
        close.clicked.connect(self.close)
        row.addWidget(brand)
        row.addStretch()
        row.addWidget(status)
        row.addSpacing(12)
        row.addWidget(close)
        return frame

    def _top_bar(self) -> QFrame:
        frame = self._panel()
        row = QHBoxLayout(frame)
        row.setContentsMargins(7, 7, 7, 7)
        row.setSpacing(8)
        sales = QPushButton("Vendas do dia  [F7]")
        sales.setObjectName("primary")
        budget = QPushButton("ORÇAMENTO DESLIGADO  [F5]")
        budget.setObjectName("inactive")
        for button in (sales, budget):
            button.setToolTip("Disponível quando o respectivo módulo for desacoplado")
            button.clicked.connect(self._unavailable_action)
            row.addWidget(button, 1)
        return frame

    def _panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        return frame

    def _customer_panel(self) -> QFrame:
        box = self._panel()
        box.setMinimumHeight(104)
        layout = QGridLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        title = QLabel("Cliente")
        title.setObjectName("muted")
        title.setStyleSheet("font-weight: 700;")
        self.customer_search = QLineEdit()
        self.customer_search.setPlaceholderText("CONSUMIDOR / ficha ou nome")
        self.customer_results = QListWidget()
        self.customer_results.setMaximumHeight(105)
        self.customer_results.hide()
        self.customer_selected = QLabel("Nenhum cliente selecionado")
        self.customer_selected.setWordWrap(True)
        clear = QPushButton("×")
        clear.setToolTip("Limpar cliente selecionado")
        clear.setFixedWidth(42)
        self.customer_search.textChanged.connect(self._search_customers)
        self.customer_results.itemActivated.connect(self._select_customer)
        self.customer_results.itemClicked.connect(self._select_customer)
        clear.clicked.connect(self._clear_customer)
        layout.addWidget(title, 0, 0, 1, 2)
        layout.addWidget(self.customer_search, 1, 0)
        layout.addWidget(clear, 1, 1)
        layout.addWidget(self.customer_results, 2, 0, 1, 2)
        layout.addWidget(self.customer_selected, 3, 0, 1, 2)
        layout.setColumnStretch(0, 1)
        return box

    def _operation_panel(self) -> QFrame:
        box = self._panel()
        layout = QGridLayout(box)
        layout.setContentsMargins(16, 11, 14, 11)
        layout.setHorizontalSpacing(7)
        layout.setVerticalSpacing(6)
        label = QLabel("Produto / código de barras")
        label.setStyleSheet("font-weight: 700;")
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("Digite o nome, código interno ou código de barras...")
        self.product_results = QListWidget()
        self.product_results.setMaximumHeight(96)
        self.product_results.hide()
        dropdown = QPushButton("▼")
        dropdown.setFixedWidth(42)
        dropdown.clicked.connect(lambda: self.product_search.setFocus())
        self.description = QLineEdit()
        self.description.setPlaceholderText("Produto selecionado")
        self.description.setReadOnly(True)
        self.quantity = QLineEdit("1")
        self.quantity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quantity.setMaximumWidth(90)
        self.price = MoneyEdit()
        self.price.setReadOnly(True)
        self.price.setMaximumWidth(145)
        self.add_button = QPushButton("Adicionar  [Enter]")
        self.add_button.setObjectName("primary")
        self.add_button.setMinimumWidth(155)
        self.loose_item = QCheckBox("Produto avulso — não cadastra e não movimenta estoque")
        loose_hint = QLabel("Descrição livre, sem baixa de estoque")
        loose_hint.setObjectName("muted")
        self.loose_item.toggled.connect(self._toggle_loose)
        self.product_search.textChanged.connect(self._search_products)
        self.product_results.itemActivated.connect(self._select_product)
        self.product_results.itemClicked.connect(self._select_product)
        self.add_button.clicked.connect(self._add_item)
        layout.addWidget(label, 0, 0)
        layout.addWidget(self.product_search, 0, 1)
        layout.addWidget(dropdown, 0, 2)
        layout.addWidget(QLabel("Qtd."), 0, 3)
        layout.addWidget(self.quantity, 0, 4)
        layout.addWidget(QLabel("Preço"), 0, 5)
        layout.addWidget(self.price, 0, 6)
        layout.addWidget(self.add_button, 0, 7)
        layout.addWidget(self.product_results, 1, 1, 1, 2)
        layout.addWidget(self.description, 1, 3, 1, 5)
        layout.addWidget(self.loose_item, 2, 1, 1, 4)
        layout.addWidget(loose_hint, 2, 5, 1, 3, Qt.AlignmentFlag.AlignRight)
        layout.setColumnStretch(1, 1)
        return box

    def _cart_panel(self) -> QFrame:
        box = self._panel()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        title = QLabel("ITENS DA VENDA")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.cart = QTableWidget(0, 4)
        self.cart.setHorizontalHeaderLabels(["Produto / Serviço", "Qtd.", "Unitário", "Total"])
        self.cart.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cart.setAlternatingRowColors(True)
        self.cart.verticalHeader().setVisible(False)
        self.cart.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cart.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.cart.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.cart.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.cart)
        return box

    def _summary_panel(self) -> QFrame:
        panel = self._panel()
        panel.setMinimumWidth(270)
        panel.setMaximumWidth(390)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        summary = QWidget()
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(14, 10, 14, 10)
        summary_layout.setSpacing(6)
        title = QLabel("RESUMO DA VENDA")
        title.setObjectName("sectionTitle")
        summary_layout.addWidget(title)
        summary_layout.addWidget(self._customer_panel())
        summary_layout.addStretch()
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {self.COLORS['border']};")
        summary_layout.addWidget(separator)
        self.total_label = QLabel("TOTAL: R$ 0,00")
        self.total_label.setObjectName("total")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_layout.addWidget(self.total_label)
        remove = QPushButton("Remover item selecionado")
        remove.setToolTip("Selecione uma linha em Itens da venda para remover")
        remove.clicked.connect(self._remove_selected_item)
        summary_layout.addWidget(remove)
        future = QLabel("AÇÕES COMERCIAIS • EM EVOLUÇÃO")
        future.setObjectName("muted")
        future.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_layout.addWidget(future)
        self.checkout_button = QPushButton("FINALIZAR VENDA  [F9]")
        self.checkout_button.setObjectName("checkout")
        self.checkout_button.clicked.connect(self._checkout)
        summary_layout.addWidget(self.checkout_button)
        layout.addWidget(summary)
        return panel

    def _footer(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("footer")
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 8, 16, 8)
        shortcuts = QLabel(
            "Enter  Selecionar / adicionar    •    F9  Finalizar venda    •    Esc  Fechar"
            "    •    F5/F7  Em preparação"
        )
        shortcuts.setObjectName("muted")
        shortcuts.setStyleSheet("font-size: 12px; font-weight: 700;")
        row.addWidget(shortcuts, 1, Qt.AlignmentFlag.AlignCenter)
        return frame

    def _install_shortcuts(self) -> None:
        self._shortcuts = []
        for sequence, callback in (
            ("Esc", self.close), ("F9", self._checkout), ("Return", self._enter_action),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _enter_action(self) -> None:
        focus = self.focusWidget()
        if focus is self.product_results and self.product_results.currentItem():
            self._select_product(self.product_results.currentItem())
            return
        if focus is self.product_search and self.product_results.count():
            self._select_product(self.product_results.currentItem() or self.product_results.item(0))
            self.quantity.setFocus()
            return
        if focus in {self.description, self.quantity, self.price, self.add_button}:
            self._add_item()

    def _unavailable_action(self) -> None:
        self.statusBar().showMessage("Funcionalidade aguardando desacoplamento comercial.", 3000)

    def _show_error(self, error: Exception) -> None:
        QMessageBox.warning(self, "NabiCode", str(error) or "Operação não concluída.")

    def _search_customers(self, term: str) -> None:
        self.customer_results.clear()
        if not term.strip():
            self.customer_results.hide()
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
        self.customer_results.setVisible(self.customer_results.count() > 0)
        if self.customer_results.count():
            self.customer_results.setCurrentRow(0)

    def _select_customer(self, item: QListWidgetItem) -> None:
        try:
            customer = self.view_model.select_customer(int(item.data(Qt.ItemDataRole.UserRole)))
            reference = customer.record_number if customer.record_number is not None else customer.code
            self.customer_selected.setText(f"Selecionado: {reference} — {customer.name}")
            self.customer_results.clear()
            self.customer_results.hide()
        except Exception as error:
            self._show_error(error)

    def _clear_customer(self) -> None:
        self.view_model.clear_customer()
        self.customer_search.clear()
        self.customer_selected.setText("Nenhum cliente selecionado")

    def _search_products(self, term: str) -> None:
        self.product_results.clear()
        if self.loose_item.isChecked() or not term.strip():
            self.product_results.hide()
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
        self.product_results.setVisible(self.product_results.count() > 0)
        if self.product_results.count():
            self.product_results.setCurrentRow(0)

    def _select_product(self, item: QListWidgetItem) -> None:
        try:
            product = self.view_model.select_product(int(item.data(Qt.ItemDataRole.UserRole)))
            self.description.setText(product.description)
            self.price.set_value(product.unit_price)
            self.product_results.clear()
            self.product_results.hide()
            self.quantity.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception as error:
            self._show_error(error)

    def _toggle_loose(self, enabled: bool) -> None:
        self.view_model.clear_product()
        self.product_search.clear()
        self.product_results.hide()
        self.product_search.setEnabled(not enabled)
        self.description.setReadOnly(not enabled)
        self.price.setReadOnly(not enabled)
        self.description.clear()
        self.description.setPlaceholderText("")
        self.price.clear_value()
        if enabled:
            self.description.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.description.setPlaceholderText("Produto selecionado")
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
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.line_id)
                if column in {1, 2, 3}:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.cart.setItem(row, column, cell)
        self.total_label.setText(f"TOTAL: R$ {MoneyCodec.format_br(self.view_model.total)}")

    def _remove_selected_item(self) -> None:
        row = self.cart.currentRow()
        if row < 0:
            self.statusBar().showMessage("Selecione um item da venda para remover.", 2500)
            return
        item = self.cart.item(row, 0)
        if item is not None:
            self._remove_item(str(item.data(Qt.ItemDataRole.UserRole)))

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
            self.customer_search.clear()
            self.refresh_cart()
        else:
            QMessageBox.warning(self, "Venda recusada", result.message)
