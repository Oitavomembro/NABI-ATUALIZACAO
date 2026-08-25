from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from commercial.application.dto import SuspendedSale
from commercial.domain.money import MoneyCodec
from .pdv_button_style import PDV_BUTTON_STYLE


class SuspendedSaleListDialog(QDialog):
    """Seleciona uma venda suspensa sem consumi-la antes da confirmação externa."""

    def __init__(
        self, suspended_sales: tuple[SuspendedSale, ...], parent=None
    ) -> None:
        super().__init__(parent)
        self.suspended_sales = suspended_sales
        self.selected_suspended_id: str | None = None
        self.setWindowTitle("Vendas suspensas")
        self.setModal(True)
        self.resize(800, 500)
        self.setStyleSheet(
            "QDialog { background:#0d1117; color:#f0f6fc; } "
            "QTableWidget { background:#161b22; color:#f0f6fc; gridline-color:#30363d; } "
            + PDV_BUTTON_STYLE
        )
        root = QVBoxLayout(self)
        title = QLabel("VENDAS SUSPENSAS")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#58a6ff;")
        root.addWidget(title)
        root.addWidget(QLabel("Reabra somente a venda que deseja devolver ao carrinho."))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Número", "Data", "Cliente", "Total"))
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, suspended in enumerate(suspended_sales):
            self.table.insertRow(row)
            values = (
                suspended.suspended_id,
                suspended.created_at.replace("T", " "),
                suspended.customer_name or "Sem cliente",
                f"R$ {MoneyCodec.format_br(suspended.total)}",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, suspended.suspended_id)
                self.table.setItem(row, column, cell)
        if suspended_sales:
            self.table.selectRow(0)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.close_button = QPushButton("Fechar  [Esc]")
        self.resume_button = QPushButton("Reabrir venda selecionada  [Enter]")
        actions.addWidget(self.close_button)
        actions.addStretch()
        actions.addWidget(self.resume_button)
        root.addLayout(actions)
        self.close_button.clicked.connect(self.reject)
        self.resume_button.clicked.connect(self._resume)
        self.table.doubleClicked.connect(self._resume)
        self._operational_widgets = (
            self.table, self.close_button, self.resume_button,
        )
        for widget in self._operational_widgets:
            widget.installEventFilter(self)
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

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
            elif watched is self.table or watched is self.resume_button:
                self._resume()
            else:
                watched.click()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _resume(self, *_args) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Vendas suspensas", "Selecione uma venda.")
            self.table.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.selected_suspended_id = str(
            self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        )
        self.accept()
