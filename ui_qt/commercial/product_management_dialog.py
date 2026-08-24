from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from commercial.application.product_dto import (
    ProductCreateCommand, ProductUpdateCommand, StockAdjustmentCommand,
    StockMovementCommand,
)
from .widgets.money_edit import MoneyEdit


STYLE = """
QDialog{background:#111316;color:#e5e9ed;font-size:14px} QLabel{color:#e5e9ed}
QLineEdit,QComboBox,QTableWidget{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #24282d,stop:1 #171a1e);color:#f1f3f5;border:1px solid #555c63;border-radius:6px;selection-background-color:#3d778d}
QLineEdit,QComboBox{min-height:40px;padding:0 9px} QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #596068,stop:0.45 #3a4046,stop:1 #272c31);color:#f4f6f8;border:1px solid #747c84;border-radius:6px;min-height:40px;padding:0 13px;font-weight:800}
QPushButton:hover{border-color:#86c7d8}
QPushButton:focus,QLineEdit:focus,QComboBox:focus,QTableWidget:focus{border:1px solid #73c7dc}
QPushButton#primary{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4f7784,stop:1 #294852);border-color:#73c7dc} QPushButton#warning{background:#73581a;border-color:#d9a928}
QHeaderView::section{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #50575e,stop:1 #292e33);color:#f2f4f6;padding:10px;border:0;border-right:1px solid #686f76;border-bottom:1px solid #73c7dc;font-weight:800}
QTableWidget{gridline-color:#41474d;alternate-background-color:#1d2024}
"""


def _money(value) -> str:
    return f"R$ {Decimal(str(value)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _quantity_text(value) -> str:
    normalized = Decimal(str(value)).quantize(Decimal("0.0001"))
    return f"{normalized:f}".rstrip("0").rstrip(".").replace(".", ",") or "0"


def _decimal(text: str, field: str) -> Decimal:
    normalized = str(text or "").strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized or "0")
    except InvalidOperation as error:
        raise ValueError(f"{field} inválido.") from error


class ProductEditorDialog(QDialog):
    def __init__(self, application, product=None, parent=None) -> None:
        super().__init__(parent)
        self.application = application; self.product = product; self.saved = None
        self.setWindowTitle("Editar produto" if product else "Novo produto")
        self.setMinimumWidth(650); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self); form = QFormLayout()
        self.code = QLineEdit(product.code if product else "")
        self.barcode = QLineEdit(product.barcode if product else "")
        self.description = QLineEdit(product.description if product else "")
        self.product_type = QComboBox(); self.product_type.addItems(("MERCADORIA", "SERVICO"))
        if product: self.product_type.setCurrentText(product.product_type)
        self.sale_price = MoneyEdit(); self.cost_price = MoneyEdit()
        self.sale_price.set_value(product.sale_price if product else 0)
        self.cost_price.set_value(product.cost_price if product else 0)
        self.current_stock = QLineEdit(_quantity_text(product.current_stock) if product else "0")
        self.minimum_stock = QLineEdit(_quantity_text(product.minimum_stock) if product else "0")
        self.allow_negative = QCheckBox("Permitir estoque negativo")
        self.allow_negative.setChecked(bool(product.allow_negative_stock) if product else False)
        if product:
            self.current_stock.setEnabled(False)
            self.current_stock.setToolTip("Use Movimentar estoque para alterar o saldo.")
        self.description.setStyleSheet(
            "font-size:18px;font-weight:900;color:#f2f4f6;border:2px solid #73c7dc"
        )
        for label, widget in (
            ("Nome / descrição*", self.description), ("Código", self.code),
            ("Código de barras", self.barcode), ("Tipo", self.product_type),
            ("Preço de venda", self.sale_price), ("Preço de custo", self.cost_price),
            ("Estoque inicial" if not product else "Estoque atual", self.current_stock),
            ("Estoque mínimo", self.minimum_stock), ("", self.allow_negative),
        ): form.addRow(label, widget)
        root.addLayout(form)
        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton("Cancelar  [Esc]"); self.save = QPushButton("Salvar  [Enter]")
        self.save.setObjectName("primary"); cancel.clicked.connect(self.reject)
        self.save.clicked.connect(self._save); row.addWidget(cancel); row.addWidget(self.save)
        root.addLayout(row)
        self._fields = (
            self.code, self.barcode, self.description, self.product_type,
            self.sale_price, self.cost_price, self.current_stock,
            self.minimum_stock, self.allow_negative, self.save,
        )
        for field in self._fields: field.installEventFilter(self)
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.setAutoRepeat(False); self._escape.activated.connect(self.reject)
        self.description.setFocus(Qt.FocusReason.OtherFocusReason)

    def _visible_fields(self):
        return tuple(field for field in self._fields if field.isEnabled() and not field.isHidden())

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            if event.isAutoRepeat(): return True
            fields = self._visible_fields(); index = fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                fields[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.save:
                self._save()
            else:
                fields[min(index + 1, len(fields) - 1)].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return super().eventFilter(watched, event)

    def _command(self):
        values = dict(
            code=self.code.text().strip(), description=self.description.text().strip(),
            barcode=self.barcode.text().strip(), product_type=self.product_type.currentText(),
            sale_price=self.sale_price.value(), cost_price=self.cost_price.value(),
            current_stock=(self.product.current_stock if self.product else _decimal(self.current_stock.text(), "Estoque inicial")),
            minimum_stock=_decimal(self.minimum_stock.text(), "Estoque mínimo"),
            allow_negative_stock=self.allow_negative.isChecked(),
        )
        return ProductUpdateCommand(**values, product_id=self.product.product_id) if self.product else ProductCreateCommand(**values)

    def _save(self) -> None:
        try:
            command = self._command()
            self.saved = self.application.update(command) if self.product else self.application.create(command)
        except Exception as error:
            QMessageBox.warning(self, "Produtos", str(error)); self.description.setFocus(); return
        self.accept()


class StockMovementDialog(QDialog):
    def __init__(self, application, product, parent=None) -> None:
        super().__init__(parent)
        self.application = application; self.product = product; self.completed = False
        self.setWindowTitle("Movimentar estoque"); self.setMinimumWidth(560); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel(product.description)
        title.setStyleSheet("font-size:21px;font-weight:900;color:#d9dee3")
        root.addWidget(title); root.addWidget(QLabel(f"Saldo atual: {_quantity_text(product.current_stock)}"))
        form = QFormLayout(); self.kind = QComboBox(); self.kind.addItems(("ENTRADA", "SAÍDA", "AJUSTE DE SALDO"))
        self.amount = QLineEdit(); self.amount.setPlaceholderText("0,0000")
        self.reason = QLineEdit(); self.reference = QLineEdit()
        form.addRow("Operação", self.kind); form.addRow("Quantidade / novo saldo", self.amount)
        form.addRow("Motivo*", self.reason); form.addRow("Referência", self.reference)
        root.addLayout(form); self.confirm = QPushButton("Revisar e confirmar  [Enter]")
        self.confirm.setObjectName("warning"); root.addWidget(self.confirm)
        self.confirm.clicked.connect(self._confirm)
        self._fields = (self.kind, self.amount, self.reason, self.reference, self.confirm)
        for field in self._fields: field.installEventFilter(self)
        self._escape = QShortcut(QKeySequence("Esc"), self); self._escape.setAutoRepeat(False)
        self._escape.activated.connect(self.reject); self.kind.setFocus()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            if event.isAutoRepeat(): return True
            index = self._fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._fields[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.confirm: self._confirm()
            else: self._fields[index + 1].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return super().eventFilter(watched, event)

    def _confirm(self) -> None:
        try:
            value = _decimal(self.amount.text(), "Quantidade")
            reason = self.reason.text().strip()
            if self.kind.currentIndex() == 2:
                command = StockAdjustmentCommand(self.product.product_id, value, reason)
                operation = self.application.adjust
            else:
                command = StockMovementCommand(
                    self.product.product_id, value, reason, self.reference.text().strip()
                )
                operation = self.application.receive if self.kind.currentIndex() == 0 else self.application.remove
        except Exception as error:
            QMessageBox.warning(self, "Estoque", str(error)); self.amount.setFocus(); return
        answer = QMessageBox.question(
            self, "Confirmar movimentação",
            f"{self.kind.currentText()} — {self.product.description}\nValor: {_quantity_text(value)}\nMotivo: {reason}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            self.confirm.setFocus(); return
        result = operation(command, confirmed=True)
        if not result.committed:
            QMessageBox.warning(self, "Estoque", result.message); self.amount.setFocus(); return
        self.completed = True; self.accept()


class StockHistoryDialog(QDialog):
    def __init__(self, product, movements, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Histórico de estoque")
        self.resize(1000, 620); self.setStyleSheet(STYLE); root = QVBoxLayout(self)
        title = QLabel(f"HISTÓRICO — {product.description}")
        title.setStyleSheet("font-size:21px;font-weight:900;color:#58a6ff"); root.addWidget(title)
        self.table = QTableWidget(0, 8); self.table.setHorizontalHeaderLabels(
            ("Data", "Tipo", "Quantidade", "Anterior", "Atual", "Origem", "Motivo", "Responsável")
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        for item in movements:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (item.occurred_at.strftime("%d/%m/%Y %H:%M"), item.movement_type,
                      _quantity_text(item.quantity), _quantity_text(item.previous_balance),
                      _quantity_text(item.resulting_balance), item.origin, item.notes, item.user)
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(str(value)))
        root.addWidget(self.table); close = QPushButton("Fechar  [Esc]"); close.clicked.connect(self.reject)
        root.addWidget(close); QShortcut(QKeySequence("Esc"), self, activated=self.reject).setAutoRepeat(False)


class ProductManagementDialog(QDialog):
    def __init__(self, application, parent=None) -> None:
        super().__init__(parent); self.application = application; self._products = ()
        self.setWindowTitle("Produtos e estoque"); self.resize(1220, 760); self.setMinimumSize(940, 620)
        self.setStyleSheet(STYLE); root = QVBoxLayout(self)
        title = QLabel("PRODUTOS E ESTOQUE")
        title.setObjectName("sectionTitle")
        title.setStyleSheet("font-size:25px;font-weight:900;color:#d9dee3;border-bottom:2px solid #73c7dc;padding:0 0 8px 2px"); root.addWidget(title)
        guidance = QLabel("Nome, preço e estoque em destaque. Cadastros e movimentos usam IDs reais e os serviços oficiais.")
        guidance.setStyleSheet("color:#8b949e"); root.addWidget(guidance)
        search_row = QHBoxLayout(); self.search = QLineEdit(); self.search.setObjectName("productSearch"); self.search.setPlaceholderText("Buscar por nome, código ou código de barras")
        refresh = QPushButton("Pesquisar  [Enter]"); refresh.clicked.connect(self.reload)
        search_row.addWidget(self.search, 1); search_row.addWidget(refresh); root.addLayout(search_row)
        self.table = QTableWidget(0, 7); self.table.setObjectName("productTable"); self.table.setAlternatingRowColors(True); self.table.setHorizontalHeaderLabels(
            ("Código", "Nome / descrição", "Preço", "Estoque", "Mínimo", "Tipo", "Situação")
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(42); self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.installEventFilter(self); self.table.doubleClicked.connect(self.edit_product)
        root.addWidget(self.table, 1)
        self.selected_details = QLabel("Selecione um produto para conferir nome, preço e estoque.")
        self.selected_details.setObjectName("productSelectedDetails")
        self.selected_details.setWordWrap(True)
        self.selected_details.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #343a40,stop:1 #1d2125);"
            "border:1px solid #666e75;border-left:4px solid #73c7dc;"
            "border-radius:6px;padding:13px;color:#f1f3f5;font-size:17px;font-weight:800;"
        )
        root.addWidget(self.selected_details)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        buttons = QHBoxLayout(); self.new = QPushButton("Novo  [F3]"); self.edit = QPushButton("Editar  [F4]")
        self.move = QPushButton("Movimentar estoque  [F6]"); self.history = QPushButton("Histórico  [F7]")
        close = QPushButton("Fechar  [Esc]"); self.new.setObjectName("primary"); self.move.setObjectName("warning")
        self.new.clicked.connect(self.new_product); self.edit.clicked.connect(self.edit_product)
        self.move.clicked.connect(self.move_stock); self.history.clicked.connect(self.show_history); close.clicked.connect(self.reject)
        for button in (self.new, self.edit, self.move, self.history): buttons.addWidget(button)
        buttons.addStretch(); buttons.addWidget(close); root.addLayout(buttons)
        self._shortcuts = []
        for key, callback in (("F3", self.new_product), ("F4", self.edit_product), ("F5", self.reload),
                              ("F6", self.move_stock), ("F7", self.show_history), ("Esc", self.reject)):
            shortcut = QShortcut(QKeySequence(key), self); shortcut.setAutoRepeat(False)
            shortcut.activated.connect(callback); self._shortcuts.append(shortcut)
        self.search.installEventFilter(self); self.search.setFocus(Qt.FocusReason.OtherFocusReason); self.reload()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            if event.isAutoRepeat(): return True
            if watched is self.search:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: return True
                self.reload(); return True
            if watched is self.table:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.search.setFocus(Qt.FocusReason.BacktabFocusReason)
                else: self.edit_product()
                return True
        return super().eventFilter(watched, event)

    def selected_id(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None: return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def reload(self) -> None:
        selected = self.selected_id()
        try: self._products = tuple(self.application.search(self.search.text(), limit=200))
        except Exception as error:
            QMessageBox.warning(self, "Produtos", str(error)); return
        self.table.setRowCount(0); selected_row = None
        for product in self._products:
            row = self.table.rowCount(); self.table.insertRow(row)
            status = "INATIVO" if not product.active else "BAIXO" if product.current_stock <= product.minimum_stock else "ATIVO"
            values = (product.code, product.description, _money(product.sale_price), _quantity_text(product.current_stock),
                      _quantity_text(product.minimum_stock), product.product_type, status)
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column == 0: cell.setData(Qt.ItemDataRole.UserRole, product.product_id)
                if column in (1, 2, 3):
                    font = cell.font(); font.setPointSize(13); font.setBold(True); cell.setFont(font)
                self.table.setItem(row, column, cell)
            if product.product_id == selected: selected_row = row
        if self.table.rowCount(): self.table.selectRow(selected_row if selected_row is not None else 0)
        else: self._show_selected_details()

    def _show_selected_details(self) -> None:
        product_id = self.selected_id()
        product = next(
            (item for item in self._products if item.product_id == product_id), None
        )
        if product is None:
            self.selected_details.setText(
                "Selecione um produto para conferir nome, preço e estoque."
            )
            return
        status = (
            "INATIVO" if not product.active else
            "ESTOQUE BAIXO" if product.current_stock <= product.minimum_stock else "ATIVO"
        )
        self.selected_details.setText(
            f"{product.description}   •   Código: {product.code or '—'}   •   "
            f"Preço: {_money(product.sale_price)}   •   "
            f"Estoque: {_quantity_text(product.current_stock)}   •   {status}"
        )

    def _selected(self):
        product_id = self.selected_id()
        if product_id is None: return None
        try: return self.application.get(product_id)
        except Exception as error: QMessageBox.warning(self, "Produtos", str(error)); return None

    def new_product(self) -> None:
        if ProductEditorDialog(self.application, parent=self).exec() == QDialog.DialogCode.Accepted: self.reload()

    def edit_product(self) -> None:
        product = self._selected()
        if product and ProductEditorDialog(self.application, product, self).exec() == QDialog.DialogCode.Accepted: self.reload()

    def move_stock(self) -> None:
        product = self._selected()
        if product and StockMovementDialog(self.application, product, self).exec() == QDialog.DialogCode.Accepted: self.reload()

    def show_history(self) -> None:
        product = self._selected()
        if not product: return
        try: movements = self.application.movements(product.product_id)
        except Exception as error: QMessageBox.warning(self, "Estoque", str(error)); return
        StockHistoryDialog(product, movements, self).exec()
