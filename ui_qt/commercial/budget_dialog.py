from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout,
)

from commercial.application.dto import BudgetDocument
from commercial.domain.money import MoneyCodec
from .pdv_button_style import PDV_BUTTON_STYLE


class _BudgetDialogBase(QDialog):
    def _keyboard_widgets(self, *widgets) -> None:
        self._operational_widgets = tuple(widgets)
        for widget in widgets:
            widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched in getattr(self, "_operational_widgets", ())
            and event.type() == QEvent.Type.KeyPress
            and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
        ):
            if event.isAutoRepeat():
                event.accept()
                return True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.focusPreviousChild()
            elif isinstance(watched, QPushButton):
                watched.click()
            else:
                self._enter_on_widget(watched)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _enter_on_widget(self, _watched) -> None:
        return None


class BudgetPreviewDialog(_BudgetDialogBase):
    """Prévia explícita; abrir ou fechar nunca imprime nem registra venda."""

    def __init__(self, view_model, budget: BudgetDocument, parent=None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self.budget = budget
        self.setWindowTitle("Orçamento salvo")
        self.setModal(True)
        self.resize(660, 620)
        self.setStyleSheet(
            "QDialog { background:#0d1117; color:#f0f6fc; } "
            "QLabel { color:#f0f6fc; } QTextBrowser { background:#161b22; color:#f0f6fc; "
            "border:1px solid #30363d; }" + PDV_BUTTON_STYLE
        )
        root = QVBoxLayout(self)
        title = QLabel("ORÇAMENTO SALVO — SEM VALOR FISCAL")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#d29922;")
        root.addWidget(title)
        root.addWidget(QLabel("Visualize, gere o PDF ou imprima somente quando desejar."))
        self.preview = QTextBrowser()
        self.preview.setPlainText(view_model.budget_preview_text(budget))
        root.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        self.close_button = QPushButton("Fechar  [Esc]")
        self.print_button = QPushButton("Imprimir orçamento")
        self.pdf_button = QPushButton("Gerar e abrir PDF")
        actions.addWidget(self.close_button)
        actions.addStretch()
        actions.addWidget(self.print_button)
        actions.addWidget(self.pdf_button)
        root.addLayout(actions)
        self.close_button.clicked.connect(self.accept)
        self.print_button.clicked.connect(self._print)
        self.pdf_button.clicked.connect(self._pdf)
        self._keyboard_widgets(self.close_button, self.print_button, self.pdf_button)
        self.close_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _print(self) -> None:
        try:
            printer = self.view_model.print_budget(self.budget)
        except Exception as error:
            QMessageBox.critical(self, "Impressão do orçamento", str(error))
            self.print_button.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        QMessageBox.information(self, "Orçamento enviado", f"Enviado para: {printer}")

    def _pdf(self) -> None:
        try:
            self.view_model.generate_budget_pdf(self.budget)
        except Exception as error:
            QMessageBox.critical(self, "PDF do orçamento", str(error))
            self.pdf_button.setFocus(Qt.FocusReason.OtherFocusReason)


class BudgetListDialog(_BudgetDialogBase):
    """Lista orçamentos abertos sem consumi-los até a escolha explícita de carregar."""

    def __init__(self, view_model, budgets: tuple[BudgetDocument, ...], parent=None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self.budgets = budgets
        self.selected_budget_id: str | None = None
        self.setWindowTitle("Orçamentos salvos")
        self.setModal(True)
        self.resize(780, 480)
        self.setStyleSheet(PDV_BUTTON_STYLE)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("ORÇAMENTOS ABERTOS — SEM VALOR FISCAL"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Número", "Data", "Cliente", "Total"))
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, budget in enumerate(budgets):
            self.table.insertRow(row)
            values = (
                budget.budget_id, budget.created_at.replace("T", " "), budget.customer_name,
                f"R$ {MoneyCodec.format_br(budget.total)}",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, budget.budget_id)
                self.table.setItem(row, column, cell)
        if budgets:
            self.table.selectRow(0)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.close_button = QPushButton("Fechar")
        self.preview_button = QPushButton("Visualizar")
        self.load_button = QPushButton("Carregar para venda")
        actions.addWidget(self.close_button)
        actions.addStretch()
        actions.addWidget(self.preview_button)
        actions.addWidget(self.load_button)
        root.addLayout(actions)
        self.close_button.clicked.connect(self.reject)
        self.preview_button.clicked.connect(self._preview)
        self.load_button.clicked.connect(self._load)
        self.table.doubleClicked.connect(self._preview)
        self._keyboard_widgets(
            self.table, self.close_button, self.preview_button, self.load_button
        )
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _selected(self) -> BudgetDocument | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        budget_id = str(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        return next((item for item in self.budgets if item.budget_id == budget_id), None)

    def _enter_on_widget(self, watched) -> None:
        if watched is self.table:
            self._preview()

    def _preview(self, *_args) -> None:
        budget = self._selected()
        if budget is None:
            QMessageBox.warning(self, "Orçamentos", "Selecione um orçamento.")
            return
        BudgetPreviewDialog(self.view_model, budget, self).exec()
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _load(self) -> None:
        budget = self._selected()
        if budget is None:
            QMessageBox.warning(self, "Orçamentos", "Selecione um orçamento.")
            return
        self.selected_budget_id = budget.budget_id
        self.accept()
