from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout,
)

from commercial.application.dto import ProductRecord
from commercial.domain.money import MoneyCodec


class ProductSearchDialog(QDialog):
    """Pesquisa ampliada e somente leitura para seleção acessível no PDV."""

    def __init__(
        self,
        search: Callable[[str, int], tuple[ProductRecord, ...]],
        parent=None,
        *,
        initial_term: str = "",
    ) -> None:
        super().__init__(parent)
        self._search = search
        self.selected_product_id: int | None = None
        self.setWindowTitle("Pesquisa ampliada de produtos")
        self.setModal(True)
        self.setMinimumSize(780, 480)
        self.resize(1020, 650)
        self.setStyleSheet(self._style_sheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        title = QLabel("PESQUISAR PRODUTO")
        title.setObjectName("title")
        hint = QLabel(
            "Digite nome, código ou código de barras. Use ↓ para acessar a lista, "
            "Enter para selecionar e Esc para voltar."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        self.search_input = QLineEdit(initial_term)
        self.search_input.setPlaceholderText("Nome, código ou código de barras")
        self.search_input.setAccessibleName("Pesquisa de produtos")

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["NOME DO PRODUTO", "PREÇO", "ESTOQUE"])
        self.table.setAccessibleName("Resultados da pesquisa de produtos")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.horizontalHeader().setMinimumHeight(48)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(2, 190)

        self.status = QLabel()
        self.status.setObjectName("status")
        buttons = QHBoxLayout()
        self.cancel_button = QPushButton("Voltar  [Esc]")
        self.select_button = QPushButton("Selecionar produto  [Enter]")
        self.select_button.setObjectName("primary")
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.select_button)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.search_input)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status)
        layout.addLayout(buttons)

        self.search_input.textChanged.connect(self._refresh)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._accept_current())
        self.select_button.clicked.connect(self._accept_current)
        self.cancel_button.clicked.connect(self.reject)
        for widget in (self.search_input, self.table, self.select_button):
            widget.installEventFilter(self)
        self._refresh(self.search_input.text())
        self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self.search_input.selectAll()

    @staticmethod
    def _style_sheet() -> str:
        return """
            QDialog { background: #0d1117; color: #f0f6fc; }
            QLabel { color: #f0f6fc; font-size: 16px; }
            QLabel#title { color: #00d084; font-size: 27px; font-weight: 800; }
            QLabel#hint, QLabel#status { color: #c9d1d9; font-size: 16px; }
            QLineEdit { background: #0d1117; color: #f0f6fc; border: 2px solid #484f58;
                border-radius: 8px; min-height: 50px; padding: 0 14px; font-size: 19px; }
            QLineEdit:focus { border-color: #1f6feb; }
            QTableWidget { background: #0d1117; color: #f0f6fc; border: 2px solid #30363d;
                gridline-color: #30363d; font-size: 18px; selection-background-color: #1f6feb; }
            QHeaderView::section { background: #21262d; color: #f0f6fc; padding: 10px;
                border: 0; border-right: 1px solid #30363d; font-size: 16px; font-weight: 800; }
            QPushButton { background: #30363d; color: #f0f6fc; border: 0; border-radius: 7px;
                min-height: 46px; padding: 0 20px; font-size: 16px; font-weight: 700; }
            QPushButton#primary { background: #1f6feb; }
            QPushButton:focus { border: 2px solid #ffffff; }
        """

    @staticmethod
    def _money(value: Decimal) -> str:
        return f"R$ {MoneyCodec.format_br(value)}"

    @staticmethod
    def _stock(value: Decimal | None) -> str:
        if value is None:
            return "Não informado"
        normalized = format(value.normalize(), "f")
        return normalized.replace(".", ",")

    def _refresh(self, term: str) -> None:
        self.selected_product_id = None
        self.table.setRowCount(0)
        try:
            records = self._search(str(term or ""), 200)
        except Exception as error:
            self.status.setText(f"Não foi possível pesquisar: {error}")
            return
        for record in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = QTableWidgetItem(record.description)
            name.setData(Qt.ItemDataRole.UserRole, record.product_id)
            price = QTableWidgetItem(self._money(record.unit_price))
            stock = QTableWidgetItem(self._stock(record.current_stock))
            price.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            stock.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, price)
            self.table.setItem(row, 2, stock)
        if self.table.rowCount():
            self.table.selectRow(0)
            self.status.setText(f"{self.table.rowCount()} produto(s) encontrado(s).")
        else:
            self.status.setText("Nenhum produto encontrado.")

    def _accept_current(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        if item is None:
            self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.selected_product_id = int(item.data(Qt.ItemDataRole.UserRole))
        self.accept()

    def eventFilter(self, watched, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.isAutoRepeat():
                event.accept()
                return True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if watched in {self.table, self.select_button}:
                    self.search_input.setFocus(Qt.FocusReason.BacktabFocusReason)
                    self.search_input.selectAll()
                event.accept()
                return True
            if watched is self.search_input:
                if self.table.rowCount():
                    self.table.setFocus(Qt.FocusReason.TabFocusReason)
                    self.table.selectRow(max(0, self.table.currentRow()))
            else:
                self._accept_current()
            event.accept()
            return True
        if watched is self.search_input and event.key() == Qt.Key.Key_Down:
            if self.table.rowCount():
                self.table.setFocus(Qt.FocusReason.TabFocusReason)
                self.table.selectRow(max(0, self.table.currentRow()))
            event.accept()
            return True
        return super().eventFilter(watched, event)
