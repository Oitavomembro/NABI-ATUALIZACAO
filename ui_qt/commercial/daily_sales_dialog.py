from __future__ import annotations

from datetime import date

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from commercial.application.dto import BudgetDocument
from commercial.application.query_dto import DailySaleSummary
from commercial.domain.money import MoneyCodec

from .budget_dialog import BudgetPreviewDialog


class DailySalePreviewDialog(QDialog):
    def __init__(self, view_model, sale: DailySaleSummary, parent=None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self.sale = sale
        self.setWindowTitle(f"Segunda via — venda #{sale.sale_id}")
        self.resize(650, 610)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("PRÉ-VISUALIZAÇÃO DO COMPROVANTE — SEGUNDA VIA"))
        self.preview = QPlainTextEdit(view_model.daily_sale_preview_text(sale))
        self.preview.setReadOnly(True)
        root.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        self.print_button = QPushButton("Imprimir segunda via")
        self.pdf_button = QPushButton("Gerar PDF")
        self.close_button = QPushButton("Fechar  [Esc]")
        self.print_button.clicked.connect(self._print)
        self.pdf_button.clicked.connect(self._pdf)
        self.close_button.clicked.connect(self.reject)
        for button in (self.print_button, self.pdf_button, self.close_button):
            button.installEventFilter(self)
            actions.addWidget(button)
        root.addLayout(actions)
        self.print_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _print(self) -> None:
        try:
            self.view_model.print_daily_sale(self.sale)
        except Exception as error:
            QMessageBox.warning(self, "Segunda via", str(error))
            self.print_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _pdf(self) -> None:
        try:
            self.view_model.generate_daily_sale_pdf(self.sale)
        except Exception as error:
            QMessageBox.warning(self, "Segunda via", str(error))
            self.pdf_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched in (self.print_button, self.pdf_button, self.close_button)
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            event.accept()
            if event.isAutoRepeat():
                return True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                order = (self.print_button, self.pdf_button, self.close_button)
                order[(order.index(watched) - 1) % len(order)].setFocus(
                    Qt.FocusReason.BacktabFocusReason
                )
                return True
            watched.click()
            return True
        return super().eventFilter(watched, event)


class DailySalesDialog(QDialog):
    def __init__(self, view_model, parent=None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self._records: list[tuple[str, DailySaleSummary | BudgetDocument]] = []
        self.setWindowTitle("Vendas do dia — reimpressão e cancelamento")
        self.resize(1080, 680)
        root = QVBoxLayout(self)
        self.title = QLabel(f"VENDAS DE HOJE — {date.today():%d/%m/%Y}")
        self.title.setStyleSheet("font-size: 21px; font-weight: 700; color: #00d084;")
        root.addWidget(self.title)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Buscar por número, cliente, horário, valor, situação ou documento"
        )
        self.refresh_button = QPushButton("Atualizar")
        self.search.textChanged.connect(self._apply_filter)
        self.refresh_button.clicked.connect(self.reload)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.refresh_button)
        root.addLayout(search_row)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ("Tipo", "Número", "Data / hora", "Cliente", "Total", "Situação", "Documento fiscal")
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(lambda *_args: self._preview())
        root.addWidget(self.table, 1)
        self.guidance = QLabel(
            "Venda não fiscal: cancelamento local. Documento fiscal: use somente a Central Fiscal."
        )
        root.addWidget(self.guidance)
        buttons = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar venda selecionada")
        self.preview_button = QPushButton("Visualizar / segunda via")
        self.close_button = QPushButton("Fechar  [Esc]")
        self.cancel_button.clicked.connect(self._cancel)
        self.preview_button.clicked.connect(self._preview)
        self.close_button.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.preview_button)
        buttons.addWidget(self.close_button)
        root.addLayout(buttons)
        for widget in (
            self.search, self.table, self.refresh_button, self.cancel_button,
            self.preview_button, self.close_button,
        ):
            widget.installEventFilter(self)
        self.reload()
        self.search.setFocus(Qt.FocusReason.OtherFocusReason)

    def reload(self) -> None:
        try:
            sales = self.view_model.list_daily_sales()
            budgets = tuple(
                item for item in self.view_model.list_budgets()
                if str(item.created_at).startswith(date.today().isoformat())
            )
        except Exception as error:
            QMessageBox.warning(self, "Vendas do dia", str(error))
            return
        self._records = [("VENDA", item) for item in sales]
        self._records.extend(("ORÇAMENTO", item) for item in budgets)
        self._apply_filter()

    def _apply_filter(self) -> None:
        wanted = self.search.text().strip().casefold()
        visible = []
        for kind, record in self._records:
            values = self._values(kind, record)
            if not wanted or wanted in " ".join(values).casefold():
                visible.append((kind, record, values))
        self.table.setRowCount(len(visible))
        for row, (kind, record, values) in enumerate(visible):
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, (kind, record))
                self.table.setItem(row, column, cell)
        if visible:
            self.table.selectRow(0)

    @staticmethod
    def _values(kind, record) -> tuple[str, ...]:
        if kind == "ORÇAMENTO":
            return (
                "ORÇAMENTO", str(record.budget_id), str(record.created_at).replace("T", " ")[:19],
                record.customer_name, f"R$ {MoneyCodec.format_br(record.total)}", "ABERTO",
                "SEM VALOR FISCAL",
            )
        fiscal = record.fiscal_status or "NÃO FISCAL"
        return (
            "VENDA", f"#{record.sale_id}", record.occurred_at,
            record.customer_name or str(record.customer_id or "CONSUMIDOR FINAL"),
            f"R$ {MoneyCodec.format_br(record.total)}", record.status or "—", fiscal,
        )

    def _selected(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _preview(self) -> None:
        selected = self._selected()
        if selected is None:
            QMessageBox.information(self, "Vendas do dia", "Selecione uma venda ou orçamento.")
            return
        kind, record = selected
        if kind == "ORÇAMENTO":
            BudgetPreviewDialog(self.view_model, record, self).exec()
        else:
            DailySalePreviewDialog(self.view_model, record, self).exec()
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _cancel(self) -> None:
        selected = self._selected()
        if selected is None:
            QMessageBox.information(self, "Vendas do dia", "Selecione uma venda.")
            return
        kind, record = selected
        if kind == "ORÇAMENTO":
            QMessageBox.information(
                self, "Vendas do dia",
                "Orçamentos não registram venda, estoque ou Caixa e não são cancelados aqui.",
            )
            return
        if record.has_fiscal_document:
            QMessageBox.information(
                self, "Cancelamento fiscal",
                "Venda vinculada a documento fiscal. Use exclusivamente a Central Fiscal.",
            )
            return
        if QMessageBox.question(
            self, "Confirmar cancelamento",
            f"Cancelar a venda #{record.sale_id} e reverter estoque e financeiro?",
        ) != QMessageBox.StandardButton.Yes:
            self.table.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        try:
            self.view_model.cancel_daily_sale(record.sale_id)
        except Exception as error:
            QMessageBox.warning(self, "Cancelar venda", str(error))
            self.table.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.reload()
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event) -> bool:
        if event.type() != QEvent.Type.KeyPress or event.key() not in (
            Qt.Key.Key_Return, Qt.Key.Key_Enter
        ):
            return super().eventFilter(watched, event)
        event.accept()
        if event.isAutoRepeat():
            return True
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if watched is self.table:
                self.search.setFocus(Qt.FocusReason.BacktabFocusReason)
            else:
                self.focusPreviousChild()
            return True
        if watched is self.search:
            if self.table.rowCount():
                self.table.setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        if watched is self.table:
            self._preview()
            return True
        watched.click()
        return True
