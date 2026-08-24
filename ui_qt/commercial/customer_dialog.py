from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QEvent, QSettings, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QInputDialog, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout,
)

from commercial.application.customer_dto import CustomerCreateCommand, CustomerUpdateCommand
from commercial.domain.money import MoneyCodec
from .widgets.money_edit import MoneyEdit


STYLE = """
QDialog { background:#111316; color:#e5e9ed; }
QLabel { color:#e5e9ed; }
QLineEdit,QTextEdit,QComboBox,QTableWidget {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #24282d,stop:1 #171a1e);
 color:#f1f3f5; border:1px solid #555c63; border-radius:6px;
 selection-background-color:#3d778d; }
QLineEdit { min-height:38px; padding:0 9px; }
QPushButton {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #596068,stop:0.45 #3a4046,stop:1 #272c31);
 color:#f4f6f8; border:1px solid #747c84; border-radius:6px;
 min-height:38px; padding:0 14px; font-weight:700; }
QPushButton:hover { border-color:#86c7d8; }
QPushButton:focus,QLineEdit:focus,QComboBox:focus,QTableWidget:focus {
 border:1px solid #73c7dc; }
QPushButton#primary {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4f7784,stop:1 #294852);
 border-color:#73c7dc; }
QPushButton#destructive { background:#7a252b; border-color:#d84a52; }
QHeaderView::section {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #50575e,stop:1 #292e33);
 color:#f2f4f6; padding:9px; border:0; border-right:1px solid #686f76;
 border-bottom:1px solid #73c7dc;
 font-weight:700; }
QTableWidget { gridline-color:#41474d; alternate-background-color:#1d2024; }
"""


def _money(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _customer_font_size() -> int:
    value = int(QSettings("NabiCode", "Fichario").value("clientes/font_size", 15))
    return max(12, min(value, 30))


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
            f"font-size:{max(20, _customer_font_size() + 4)}px;font-weight:900;"
            "color:#f2f4f6;border:2px solid #73c7dc"
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
        title.setStyleSheet("font-size:21px;font-weight:800;color:#d9dee3")
        layout.addWidget(title)
        contact = QLabel(
            f"Endereço: {customer.address or '—'}   •   "
            f"Telefone: {customer.phone or '—'}"
        )
        contact.setWordWrap(True)
        contact.setStyleSheet("font-size:15px;font-weight:700;color:#c9d1d9")
        layout.addWidget(contact)
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
    def __init__(
        self, service, parent=None, *, customer_provider=None, filter_title="",
        deletion_authorizer=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.customer_provider = customer_provider
        self.deletion_authorizer = deletion_authorizer
        self.setWindowTitle("Clientes e fichas")
        self.resize(1180, 720)
        self.setMinimumSize(940, 600)
        self.setStyleSheet(_customer_style())
        layout = QVBoxLayout(self)
        title = QLabel("CLIENTES E FICHAS")
        title.setObjectName("sectionTitle")
        title.setStyleSheet(
            "font-size:25px;font-weight:900;color:#d9dee3;"
            "border-bottom:2px solid #73c7dc;padding:0 0 8px 2px"
        )
        layout.addWidget(title)
        if filter_title:
            active_filter = QLabel(f"Filtro ativo: {filter_title}")
            active_filter.setStyleSheet("font-size:16px;font-weight:800;color:#ffd33d")
            layout.addWidget(active_filter)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("customerSearch")
        self.search.setPlaceholderText(
            "Buscar por ficha, código, nome, CPF, RG, telefone ou endereço"
        )
        self.refresh_button = QPushButton("Atualizar  [F5]")
        self.refresh_button.clicked.connect(self.reload)
        self.font_size = QComboBox()
        self.font_size.addItems(tuple(str(value) for value in range(12, 31)))
        self.font_size.setCurrentText(str(_customer_font_size()))
        self.font_size.setToolTip("Tamanho das letras desta área")
        self.font_size.currentTextChanged.connect(self._change_font_size)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(QLabel("Letras")); search_row.addWidget(self.font_size)
        search_row.addWidget(self.refresh_button)
        layout.addLayout(search_row)
        self.table = QTableWidget(0, 6)
        self.table.setObjectName("customerTable")
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(
            [
                "Ficha", "Nome", "Saldo\ndevedor", "Compras\nsem atraso",
                "Compras\ncom atraso", "Parcelas\natrasadas",
            ]
        )
        header_tips = (
            "Número da ficha do cliente.",
            "Nome cadastrado do cliente.",
            "Valor que o cliente ainda deve.",
            "Compras confiáveis em que nenhuma parcela atrasou.",
            "Compras confiáveis com pelo menos uma parcela atrasada.",
            "Total de parcelas pagas com atraso ou vencidas em aberto.",
        )
        for index, tip in enumerate(header_tips):
            self.table.horizontalHeaderItem(index).setToolTip(tip)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setMinimumHeight(58)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 96)
        self.table.doubleClicked.connect(self.open_statement)
        self.table.installEventFilter(self)
        self.search.installEventFilter(self)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.reload)
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        self._apply_customer_font(_customer_font_size())
        layout.addWidget(self.table, 1)
        self.selected_details = QLabel("Selecione um cliente para ver o endereço.")
        self.selected_details.setObjectName("customerSelectedDetails")
        self.selected_details.setWordWrap(True)
        self.selected_details.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #343a40,stop:1 #1d2125);"
            "border:1px solid #666e75;border-left:4px solid #73c7dc;"
            "border-radius:6px;padding:13px;color:#f1f3f5;font-size:18px;font-weight:800;"
        )
        layout.addWidget(self.selected_details)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        buttons = QHBoxLayout()
        self.new_button = QPushButton("Novo cliente  [F3]")
        self.edit_button = QPushButton("Editar selecionado  [F4]")
        self.statement_button = QPushButton("Abrir ficha  [Enter]")
        self.delete_button = QPushButton("Excluir cadastro vazio  [Del]")
        self.delete_button.setObjectName("destructive")
        close = QPushButton("Fechar  [Esc]")
        self.new_button.setObjectName("primary")
        self.new_button.clicked.connect(self.new_customer)
        self.edit_button.clicked.connect(self.edit_customer)
        self.statement_button.clicked.connect(self.open_statement)
        self.delete_button.clicked.connect(self.delete_customer)
        close.clicked.connect(self.reject)
        for button in (
            self.new_button, self.edit_button, self.statement_button, self.delete_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(); buttons.addWidget(close)
        layout.addLayout(buttons)
        self._shortcuts = []
        for key, callback in (
            ("F3", self.new_customer), ("F4", self.edit_customer),
            ("F5", self.reload), ("Del", self.delete_customer), ("Esc", self.reject),
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
        size = max(12, min(int(value), 30))
        QSettings("NabiCode", "Fichario").setValue("clientes/font_size", size)
        QSettings("NabiCode", "Fichario").setValue("interface/font_size", size)
        self.setStyleSheet(_customer_style(size))
        self._apply_customer_font(size)

    def _apply_customer_font(self, size: int) -> None:
        self.search.setStyleSheet(
            f"font-size:{size + 2}px;font-weight:800;min-height:{size + 30}px;"
        )
        self.table.setStyleSheet(f"font-size:{size}px;")
        self.table.verticalHeader().setDefaultSectionSize(size + 22)

    def reload(self) -> None:
        try:
            term = self.search.text().strip()
            limit = 200 if term else 60
            customers = (
                self.customer_provider(term, limit)
                if self.customer_provider is not None
                else self.service.list_customers(term, limit=limit)
            )
        except Exception as exc:
            QMessageBox.warning(self, "Clientes", str(exc)); return
        self.table.setRowCount(0)
        self._customers_by_id = {}
        behavior_loader = getattr(self.service, "customer_purchase_behavior", None)
        behaviors = (
            behavior_loader(tuple(customer.customer_id for customer in customers))
            if callable(behavior_loader) else ()
        )
        behavior_by_id = {item.customer_id: item for item in behaviors}
        for customer in customers:
            self._customers_by_id[customer.customer_id] = customer
            behavior = behavior_by_id.get(customer.customer_id)
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (
                customer.record_number or "—", customer.name,
                _money(customer.debt_balance),
                behavior.on_time_purchases if behavior else 0,
                behavior.delayed_purchases if behavior else 0,
                behavior.delay_count if behavior else 0,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 1:
                    item.setToolTip(
                        f"Ficha {customer.record_number or '—'} — {customer.name}\n"
                        f"Endereço: {customer.address or '—'}\n"
                        f"Telefone: {customer.phone or '—'}"
                    )
                if behavior and behavior.unclassified_purchases and column in {3, 4, 5}:
                    item.setToolTip(
                        f"{behavior.unclassified_purchases} compra(s) antiga(s) sem dados "
                        "confiáveis de parcelas não entram nesta classificação."
                    )
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

    def _show_selected_details(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            self.selected_details.setText("Selecione um cliente para ver o endereço.")
            return
        customer_id = self.selected_customer_id()
        customer = self._customers_by_id.get(customer_id)
        if customer is None:
            self.selected_details.setText("Selecione um cliente para ver os dados.")
            return
        parts = [f"Ficha {customer.record_number or '—'} — {customer.name}"]
        if customer.address.strip(): parts.append(f"Endereço: {customer.address.strip()}")
        if customer.cpf.strip(): parts.append(f"CPF: {customer.cpf.strip()}")
        if customer.phone.strip(): parts.append(f"Telefone: {customer.phone.strip()}")
        self.selected_details.setText("   •   ".join(parts))

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

    def delete_customer(self) -> None:
        customer = self._selected()
        if customer is None:
            return
        if self.deletion_authorizer is None or not self.deletion_authorizer():
            return
        reference = customer.record_number or "—"
        typed, accepted = QInputDialog.getText(
            self, "Excluir cadastro vazio",
            f"Ficha {reference} — {customer.name}\n\n"
            "Somente cadastros sem saldo e sem movimentos podem ser excluídos.\n"
            "Digite EXCLUIR para confirmar:",
        )
        if not accepted or typed.strip().upper() != "EXCLUIR":
            return
        try:
            self.service.delete_unused_customer(customer.customer_id)
        except Exception as exc:
            QMessageBox.warning(self, "Exclusão recusada", str(exc))
            return
        QMessageBox.information(self, "Cliente", "Cadastro vazio excluído com segurança.")
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
