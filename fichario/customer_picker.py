from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QMessageBox,
)
from ui_qt.commercial.customer_dialog import STYLE, _money


class CustomerPickerDialog(QDialog):
    """Consulta limitada; seleção explícita por ID, sem escrever dados."""

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.selected_customer = None
        self.setWindowTitle("Selecionar cliente")
        self.resize(1000, 620)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("ESCOLHA O CLIENTE — ficha, nome e saldo"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Digite ficha ou nome e pressione Enter para buscar")
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Ficha", "Nome", "Telefone", "Saldo devedor", "Situação"))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(44)
        layout.addWidget(self.table)
        self.notice = QLabel("Até 100 clientes por busca; refine pelo nome ou ficha.")
        layout.addWidget(self.notice)
        select = QPushButton("Selecionar cliente  [Enter]")
        select.setAutoDefault(False)
        select.clicked.connect(self.choose)
        layout.addWidget(select)
        close = QPushButton("Cancelar  [Esc]")
        close.setAutoDefault(False)
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        self.table.doubleClicked.connect(self.choose)
        self.search.installEventFilter(self)
        self.table.installEventFilter(self)
        self.reload()
        self.search.setFocus()

    def reload(self):
        self.selected_customer = None
        self.table.setRowCount(0)
        try:
            self.rows = tuple(self.service.list_customers(self.search.text().strip(), limit=100))
        except Exception as error:
            self.rows = ()
            QMessageBox.warning(self, "Clientes", str(error))
            return
        for row, customer in enumerate(self.rows):
            self.table.insertRow(row)
            values = (customer.record_number or "—", customer.name, customer.phone,
                      _money(customer.debt_balance),
                      "DEVENDO" if customer.debt_balance > 0 else "EM DIA")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, customer.customer_id)
                self.table.setItem(row, column, item)
        if self.rows:
            self.table.selectRow(0)
        self.notice.setText(f"{len(self.rows)} cliente(s) exibido(s). Limite: 100; refine a busca.")

    def choose(self, *_args):
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            try:
                self.selected_customer = self.service.get_customer(self.rows[row].customer_id)
            except Exception as error:
                QMessageBox.warning(self, "Cliente", str(error))
                return
            self.accept()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not event.isAutoRepeat():
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.search.setFocus()
                elif watched is self.search:
                    self.reload()
                    self.table.setFocus()
                else:
                    self.choose()
            return True
        return super().eventFilter(watched, event)
