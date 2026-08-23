from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QEvent, QSettings, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout,
)

from commercial.application.customer_dto import CustomerCreateCommand, CustomerUpdateCommand
from commercial.domain.money import MoneyCodec
from .widgets.money_edit import MoneyEdit


STYLE = """
QDialog { background:#0d1117; color:#f0f6fc; }
QLabel { color:#f0f6fc; }
QLineEdit,QTextEdit,QTableWidget { background:#161b22; color:#f0f6fc;
 border:1px solid #30363d; border-radius:6px; selection-background-color:#1f6feb; }
QLineEdit { min-height:38px; padding:0 9px; }
QPushButton { background:#30363d; color:#f0f6fc; border:0; border-radius:6px;
 min-height:38px; padding:0 14px; font-weight:700; }
QPushButton#primary { background:#1f6feb; }
QHeaderView::section { background:#21262d; color:#f0f6fc; padding:9px;
 border:0; border-right:1px solid #30363d; font-weight:700; }
"""


def _money(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _customer_font_size() -> int:
    value = int(QSettings("NabiCode", "Fichario").value("clientes/font_size", 15))
    return max(13, min(value, 22))


def _customer_style(size: int | None = None) -> str:
    return STYLE + f"\nQDialog {{ font-size:{size or _customer_font_size()}px; }}"


class CustomerEditorDialog(QDialog):
    def __init__(self, service, customer=None, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.customer = customer
        self.saved_customer = None
        self.setWindowTitle("Editar cliente" if customer else "Novo cliente")
        self.setMinimumWidth(620)
        self.setStyleSheet(_customer_style())
        layout = QVBoxLayout(self)
        form = QFormLayout()
        next_record = getattr(service, "next_record_number", lambda: 5500)
        self.record = QLineEdit(
            str(customer.record_number or "") if customer else str(next_record())
        )
        self.record.setStyleSheet(
            "font-size:20px;font-weight:900;color:#00d084;border:2px solid #00d084"
        )
        self.name = QLineEdit(customer.name if customer else "")
        self.code = QLineEdit(customer.code if customer else "")
        self.cpf = QLineEdit(customer.cpf if customer else "")
        self.rg = QLineEdit(customer.rg if customer else "")
        self.phone = QLineEdit(customer.phone if customer else "")
        self.address = QLineEdit(customer.address if customer else "")
        self.notes = QTextEdit(customer.notes if customer else "")
        self.notes.setMaximumHeight(90)
        self.limit = MoneyEdit()
        self.limit.set_value(customer.credit_limit if customer else Decimal("0"))
        for label, widget in (
            ("NÚMERO DA FICHA*", self.record), ("Código", self.code), ("Nome*", self.name),
            ("CPF", self.cpf), ("RG", self.rg), ("Telefone", self.phone),
            ("Endereço", self.address), ("Observações", self.notes),
            ("Limite de crédito", self.limit),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancelar  [Esc]")
        self.save_button = QPushButton("Salvar  [Enter]")
        self.save_button.setObjectName("primary")
        cancel.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self._fields = (
            self.record, self.code, self.name, self.cpf, self.rg, self.phone,
            self.address, self.notes, self.limit, self.save_button,
        )
        for widget in self._fields:
            widget.installEventFilter(self)
        self.record.setFocus(Qt.FocusReason.OtherFocusReason)
        self.record.selectAll()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.isAutoRepeat():
                event.accept(); return True
            index = self._fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._fields[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.save_button:
                self._save()
            else:
                self._fields[min(len(self._fields) - 1, index + 1)].setFocus(
                    Qt.FocusReason.TabFocusReason
                )
            event.accept(); return True
        return super().eventFilter(watched, event)

    def _save(self) -> None:
        try:
            record = int(self.record.text()) if self.record.text().strip() else None
            values = dict(
                name=self.name.text(), code=self.code.text(), record_number=record,
                cpf=self.cpf.text(), rg=self.rg.text(), phone=self.phone.text(),
                address=self.address.text(), notes=self.notes.toPlainText(),
                credit_limit=self.limit.value(),
            )
            if self.customer is None:
                self.saved_customer = self.service.create_customer(CustomerCreateCommand(**values))
            else:
                self.saved_customer = self.service.update_customer(CustomerUpdateCommand(
                    customer_id=self.customer.customer_id, **values
                ))
        except Exception as exc:
            QMessageBox.warning(self, "Cliente", str(exc))
            self.record.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.accept()


class CustomerStatementDialog(QDialog):
    def __init__(self, statement, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Ficha do cliente — {statement.customer.name}")
        self.resize(900, 620)
        self.setStyleSheet(_customer_style())
        layout = QVBoxLayout(self)
        customer = statement.customer
        title = QLabel(f"FICHA {customer.record_number or '—'} — {customer.name}")
        title.setStyleSheet("font-size:21px;font-weight:800;color:#00d084")
        layout.addWidget(title)
        summary = QLabel(
            f"Saldo devedor: {_money(customer.debt_balance)}   •   "
            f"Limite: {_money(customer.credit_limit)}   •   "
            f"Disponível: {_money(customer.available_credit)}   •   "
            f"Vencido: {_money(statement.overdue_amount)}"
        )
        summary.setStyleSheet("font-size:15px;font-weight:700")
        layout.addWidget(summary)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Data", "Tipo", "Descrição", "Débito", "Crédito", "Situação"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for entry in statement.entries:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (
                entry.occurred_at, entry.movement_type, entry.description,
                _money(entry.debit), _money(entry.credit), entry.status,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        layout.addWidget(self.table)
        close = QPushButton("Fechar  [Esc]")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        QShortcut(QKeySequence("Esc"), self, activated=self.reject).setAutoRepeat(False)
        close.setFocus(Qt.FocusReason.OtherFocusReason)


class CustomerManagementDialog(QDialog):
    def __init__(self, service, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Clientes e fichas")
        self.resize(1100, 700)
        self.setMinimumSize(820, 540)
        self.setStyleSheet(_customer_style())
        layout = QVBoxLayout(self)
        title = QLabel("CLIENTES E FICHAS")
        title.setStyleSheet("font-size:23px;font-weight:800;color:#00d084")
        layout.addWidget(title)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Buscar por ficha, código, nome, CPF, RG, telefone ou endereço"
        )
        self.refresh_button = QPushButton("Atualizar  [F5]")
        self.refresh_button.clicked.connect(self.reload)
        self.font_size = QComboBox()
        self.font_size.addItems(("13", "15", "17", "19", "21"))
        self.font_size.setCurrentText(str(_customer_font_size()))
        self.font_size.setToolTip("Tamanho das letras desta área")
        self.font_size.currentTextChanged.connect(self._change_font_size)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(QLabel("Letras")); search_row.addWidget(self.font_size)
        search_row.addWidget(self.refresh_button)
        layout.addLayout(search_row)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Ficha", "Nome", "Telefone", "Saldo", "Limite", "Disponível"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.open_statement)
        self.table.installEventFilter(self)
        self.search.installEventFilter(self)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.reload)
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.new_button = QPushButton("Novo cliente  [F3]")
        self.edit_button = QPushButton("Editar selecionado  [F4]")
        self.statement_button = QPushButton("Abrir ficha  [Enter]")
        close = QPushButton("Fechar  [Esc]")
        self.new_button.setObjectName("primary")
        self.new_button.clicked.connect(self.new_customer)
        self.edit_button.clicked.connect(self.edit_customer)
        self.statement_button.clicked.connect(self.open_statement)
        close.clicked.connect(self.reject)
        for button in (self.new_button, self.edit_button, self.statement_button):
            buttons.addWidget(button)
        buttons.addStretch(); buttons.addWidget(close)
        layout.addLayout(buttons)
        self._shortcuts = []
        for key, callback in (
            ("F3", self.new_customer), ("F4", self.edit_customer),
            ("F5", self.reload), ("Esc", self.reject),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setAutoRepeat(False); shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        self.reload()
        self.search.setFocus(Qt.FocusReason.OtherFocusReason)

    def selected_customer_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _change_font_size(self, value: str) -> None:
        size = max(13, min(int(value), 22))
        QSettings("NabiCode", "Fichario").setValue("clientes/font_size", size)
        self.setStyleSheet(_customer_style(size))
        self.table.verticalHeader().setDefaultSectionSize(size + 22)

    def reload(self) -> None:
        try:
            term = self.search.text().strip()
            customers = self.service.list_customers(term, limit=200 if term else 60)
        except Exception as exc:
            QMessageBox.warning(self, "Clientes", str(exc)); return
        self.table.setRowCount(0)
        for customer in customers:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (
                customer.record_number or "—", customer.name, customer.phone or "—",
                _money(customer.debt_balance), _money(customer.credit_limit),
                _money(customer.available_credit),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, customer.customer_id)
                    font = item.font(); font.setBold(True); font.setPointSize(font.pointSize() + 2)
                    item.setFont(font)
                balance = customer.debt_balance
                color = "#f0f6fc"
                if balance > Decimal("500.00"):
                    color = "#ff7b72"
                elif balance > Decimal("0.005"):
                    color = "#ffd33d"
                item.setForeground(QBrush(QColor(color)))
                self.table.setItem(row, column, item)
        if self.table.rowCount(): self.table.selectRow(0)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.isAutoRepeat(): event.accept(); return True
            if watched is self.search:
                self.reload(); self.table.setFocus(Qt.FocusReason.TabFocusReason)
            elif watched is self.table:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.search.setFocus(Qt.FocusReason.BacktabFocusReason)
                else:
                    self.open_statement()
            event.accept(); return True
        return super().eventFilter(watched, event)

    def _selected(self):
        customer_id = self.selected_customer_id()
        if customer_id is None:
            QMessageBox.information(self, "Clientes", "Selecione um cliente.")
            return None
        return self.service.get_customer(customer_id)

    def new_customer(self) -> None:
        dialog = CustomerEditorDialog(self.service, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.reload()

    def edit_customer(self) -> None:
        customer = self._selected()
        if customer is None: return
        if CustomerEditorDialog(self.service, customer, self).exec() == QDialog.DialogCode.Accepted:
            self.reload()

    def open_statement(self, *_args) -> None:
        customer_id = self.selected_customer_id()
        if customer_id is None:
            QMessageBox.information(self, "Clientes", "Selecione um cliente."); return
        try:
            statement = self.service.customer_statement(customer_id)
        except Exception as exc:
            QMessageBox.warning(self, "Clientes", str(exc)); return
        CustomerStatementDialog(statement, self).exec()
