from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QTextBrowser, QVBoxLayout,
)

from commercial.application.dto import BudgetDocument
from commercial.domain.money import MoneyCodec
from .widgets.money_edit import MoneyEdit


class BudgetTermsDialog(QDialog):
    """Coleta somente uma simulação; nunca cria pagamento ou título."""

    def __init__(self, total, parent=None) -> None:
        super().__init__(parent)
        self.total = MoneyCodec.parse(total, field="total do orçamento")
        self.setWindowTitle("Condições estimadas do orçamento")
        self.setModal(True)
        self.resize(480, 280)
        root = QVBoxLayout(self)
        warning = QLabel(
            "Isto é apenas uma proposta. Não registra recebimento, crediário, "
            "Caixa, estoque, ficha ou documento fiscal."
        )
        warning.setWordWrap(True)
        root.addWidget(warning)
        form = QFormLayout()
        self.method = QComboBox()
        self.method.addItems(("A COMBINAR", "DINHEIRO", "PIX", "DÉBITO", "CRÉDITO", "CREDIÁRIO", "OUTROS"))
        self.entry = MoneyEdit()
        self.entry.set_value(0)
        self.installments = QSpinBox()
        self.installments.setRange(1, 120)
        self.summary = QLabel()
        form.addRow("Forma pretendida", self.method)
        form.addRow("Entrada estimada", self.entry)
        form.addRow("Quantidade de parcelas", self.installments)
        form.addRow("Simulação", self.summary)
        root.addLayout(form)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar orçamento")
        root.addWidget(self.buttons)
        self.entry.textChanged.connect(self._refresh)
        self.installments.valueChanged.connect(self._refresh)
        self.buttons.accepted.connect(self._accept_validated)
        self.buttons.rejected.connect(self.reject)
        self._refresh()

    def _refresh(self, *_args) -> None:
        entry = self.entry.value()
        financed = max(MoneyCodec.ZERO, self.total - entry)
        count = self.installments.value()
        installment = (financed / count).quantize(MoneyCodec.CENT) if count else financed
        self.summary.setText(
            f"R$ {MoneyCodec.format_br(entry)} de entrada + {count}x de "
            f"aprox. R$ {MoneyCodec.format_br(installment)}"
        )

    def _accept_validated(self) -> None:
        if self.entry.value() > self.total:
            QMessageBox.warning(
                self, "Orçamento", "A entrada estimada não pode superar o total."
            )
            self.entry.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.accept()

    @property
    def terms(self) -> dict:
        return {
            "payment_method": self.method.currentText(),
            "entry_amount": self.entry.value(),
            "installments": self.installments.value(),
        }


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
            "border:1px solid #30363d; } QPushButton { padding:9px 14px; }"
        )
        root = QVBoxLayout(self)
        title = QLabel("ORÇAMENTO SALVO — SEM VALOR FISCAL")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#d29922;")
        root.addWidget(title)
        root.addWidget(QLabel("Visualize, gere o PDF ou imprima somente quando desejar."))
        financed = budget.total - budget.entry_amount
        terms = QLabel(
            f"Condição estimada: {budget.payment_method} • "
            f"entrada R$ {MoneyCodec.format_br(budget.entry_amount)} • "
            f"saldo R$ {MoneyCodec.format_br(financed)} em {budget.installments}x"
        )
        terms.setWordWrap(True)
        root.addWidget(terms)
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
        self.open_legacy_drafts = False
        self.setWindowTitle("Orçamentos salvos")
        self.setModal(True)
        self.resize(780, 480)
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
        self.legacy_button = QPushButton("Rascunhos antigos")
        self.legacy_button.setToolTip("Recuperar vendas suspensas salvas na versão anterior")
        self.preview_button = QPushButton("Visualizar")
        self.load_button = QPushButton("Carregar para venda")
        actions.addWidget(self.close_button)
        actions.addWidget(self.legacy_button)
        actions.addStretch()
        actions.addWidget(self.preview_button)
        actions.addWidget(self.load_button)
        root.addLayout(actions)
        self.close_button.clicked.connect(self.reject)
        self.legacy_button.clicked.connect(self._open_legacy)
        self.preview_button.clicked.connect(self._preview)
        self.load_button.clicked.connect(self._load)
        self.table.doubleClicked.connect(self._preview)
        self._keyboard_widgets(
            self.table, self.close_button, self.legacy_button, self.preview_button, self.load_button
        )
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_legacy(self) -> None:
        self.open_legacy_drafts = True
        self.accept()

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
