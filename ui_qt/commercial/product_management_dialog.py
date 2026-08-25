from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QFileDialog, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from commercial.application.product_dto import (
    ProductCreateCommand, ProductUpdateCommand, StockAdjustmentCommand,
    StockMovementCommand,
)
from administration.product_xml_import_service import ProductXMLDecision
from .nfe_purchase_import_dialog import NFePurchaseImportDialog
from .widgets.money_edit import MoneyEdit


STYLE = """
QDialog{background:#0d1117;color:#f0f6fc;font-size:14px} QLabel{color:#f0f6fc}
QLineEdit,QComboBox,QTableWidget{background:#161b22;color:#f0f6fc;border:1px solid #30363d;border-radius:6px;selection-background-color:#1f6feb}
QLineEdit,QComboBox{min-height:38px;padding:0 8px} QPushButton{background:#30363d;color:#f0f6fc;border:0;border-radius:6px;min-height:40px;padding:0 13px;font-weight:800}
QPushButton#primary{background:#238636} QPushButton#warning{background:#9e6a03}
QHeaderView::section{background:#21262d;color:#f0f6fc;padding:10px;border:0;border-right:1px solid #30363d;font-weight:800}
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
        for label, widget in (
            ("Código", self.code), ("Código de barras", self.barcode),
            ("Nome / descrição*", self.description), ("Tipo", self.product_type),
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
        title.setStyleSheet("font-size:21px;font-weight:900;color:#00d084")
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


class ProductXMLReviewDialog(QDialog):
    """Área de trabalho para revisão; nunca interpreta protocolo como autorização."""

    COLUMNS = (
        "Decisão", "Item", "Código", "Descrição", "Código de barras",
        "NCM", "CEST", "Un.", "Custo do XML", "Preço de venda", "Fonte / alertas",
    )

    def __init__(self, application, draft, parent=None) -> None:
        super().__init__(parent)
        self.application = application
        self.draft = draft
        self.result_data = None
        self._submitting = False
        self._decision_boxes: list[QComboBox] = []
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("Preparar cadastros por XML")
        self.resize(1380, 780)
        self.setMinimumSize(1040, 620)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("REVISAR PRODUTOS DO XML LOCAL")
        title.setStyleSheet("font-size:24px;font-weight:900;color:#58a6ff")
        root.addWidget(title)
        source = QLabel(
            f"Fonte local: {draft.source_name}  •  SHA-256: {draft.source_sha256}"
        )
        source.setTextFormat(Qt.TextFormat.PlainText)
        source.setWordWrap(True)
        root.addWidget(source)
        limits = QLabel("\n".join(f"• {warning}" for warning in draft.warnings))
        limits.setTextFormat(Qt.TextFormat.PlainText)
        limits.setWordWrap(True)
        limits.setStyleSheet(
            "background:#161b22;border-left:5px solid #d29922;padding:10px;font-weight:700"
        )
        root.addWidget(limits)
        self.table = QTableWidget(len(draft.items), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)
        for row, item in enumerate(draft.items):
            decision = QComboBox()
            if item.state == "NOVO":
                decision.addItem("Cadastrar após confirmar", ("CREATE", None))
                decision.addItem("Não cadastrar", ("SKIP", None))
            elif item.state == "JA_CADASTRADO":
                match = item.matches[0]
                decision.addItem(
                    f"Usar cadastro ID {match.product_id}",
                    ("USE_EXISTING", match.product_id),
                )
            elif item.state == "AMBIGUO":
                decision.addItem("Escolha o cadastro correto…", ("", None))
                for match in item.matches:
                    decision.addItem(
                        f"ID {match.product_id} — {match.description}",
                        ("USE_EXISTING", match.product_id),
                    )
            else:
                decision.addItem(
                    f"Ignorar repetição do item {item.duplicate_of_item}",
                    ("SKIP", None),
                )
            self._decision_boxes.append(decision)
            self.table.setCellWidget(row, 0, decision)
            values = (
                str(item.source_item), item.code, item.description, item.barcode,
                item.ncm, item.cest, item.unit,
                format(item.cost_price, ".2f").replace(".", ","), "0,00",
                f"Item {item.source_item} do XML local. " + " ".join(item.warnings),
            )
            editable = item.state == "NOVO"
            for offset, value in enumerate(values, start=1):
                cell = QTableWidgetItem(value)
                if offset in {1, 10} or not editable:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setToolTip(value)
                self.table.setItem(row, offset, cell)
        root.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel = QPushButton("Cancelar  [Esc]")
        self.confirm = QPushButton("Confirmar cadastros  [Enter]")
        self.confirm.setObjectName("primary")
        self.cancel.clicked.connect(self.reject)
        self.confirm.clicked.connect(self._commit)
        buttons.addWidget(self.cancel)
        buttons.addWidget(self.confirm)
        root.addLayout(buttons)
        self._navigation = (self.table, self.confirm, self.cancel)
        for widget in self._navigation:
            widget.installEventFilter(self)
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.setAutoRepeat(False)
        self._escape.activated.connect(self.reject)
        if self.table.rowCount():
            self.table.selectRow(0)
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    @staticmethod
    def _table_decimal(text: str, field: str) -> Decimal:
        return _decimal(text, field)

    def decisions(self) -> tuple[ProductXMLDecision, ...]:
        decisions = []
        for row, item in enumerate(self.draft.items):
            action, existing_id = self._decision_boxes[row].currentData()
            decisions.append(ProductXMLDecision(
                source_item=item.source_item,
                action=action,
                existing_product_id=existing_id,
                code=self.table.item(row, 2).text().strip(),
                description=self.table.item(row, 3).text().strip(),
                barcode=self.table.item(row, 4).text().strip(),
                ncm=self.table.item(row, 5).text().strip(),
                cest=self.table.item(row, 6).text().strip(),
                unit=self.table.item(row, 7).text().strip(),
                cost_price=self._table_decimal(self.table.item(row, 8).text(), "Custo"),
                sale_price=self._table_decimal(
                    self.table.item(row, 9).text(), "Preço de venda"
                ),
            ))
        return tuple(decisions)

    def _commit(self) -> None:
        if self._submitting:
            return
        try:
            decisions = self.decisions()
        except Exception as error:
            QMessageBox.warning(self, "Revisar produtos", str(error))
            self.table.setFocus()
            return
        creates = sum(decision.action == "CREATE" for decision in decisions)
        existing = sum(decision.action == "USE_EXISTING" for decision in decisions)
        answer = QMessageBox.question(
            self,
            "Confirmar cadastros",
            f"Criar {creates} cadastro(s) e reconhecer {existing} existente(s)?\n\n"
            "Estoque inicial será zero. Nenhuma compra, financeiro, autorização fiscal "
            "ou comunicação SEFAZ será criada.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            self.confirm.setFocus()
            return
        self._submitting = True
        self.confirm.setEnabled(False)
        try:
            self.result_data = self.application.commit_xml(
                self.draft, decisions, confirmed=True,
            )
        except Exception as error:
            self._submitting = False
            self.confirm.setEnabled(True)
            QMessageBox.warning(self, "Cadastros não realizados", str(error))
            self.table.setFocus()
            return
        self.accept()

    def eventFilter(self, watched, event) -> bool:
        if watched in self._navigation and event.type() == QEvent.Type.KeyPress:
            if event.key() not in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                return super().eventFilter(watched, event)
            event.accept()
            if event.isAutoRepeat():
                return True
            index = self._navigation.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._navigation[max(0, index - 1)].setFocus(
                    Qt.FocusReason.BacktabFocusReason
                )
            elif watched is self.confirm:
                self._commit()
            elif watched is self.cancel:
                self.reject()
            else:
                self._navigation[min(index + 1, len(self._navigation) - 1)].setFocus(
                    Qt.FocusReason.TabFocusReason
                )
            return True
        return super().eventFilter(watched, event)


class ProductManagementDialog(QDialog):
    def __init__(self, application, parent=None) -> None:
        super().__init__(parent); self.application = application; self._products = ()
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("Produtos e estoque"); self.resize(1220, 760); self.setMinimumSize(940, 620)
        self.setStyleSheet(STYLE); root = QVBoxLayout(self)
        title = QLabel("PRODUTOS E ESTOQUE")
        title.setStyleSheet("font-size:25px;font-weight:900;color:#00d084"); root.addWidget(title)
        guidance = QLabel("Nome, preço e estoque em destaque. Cadastros e movimentos usam IDs reais e os serviços oficiais.")
        guidance.setStyleSheet("color:#8b949e"); root.addWidget(guidance)
        search_row = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText("Buscar por nome, código ou código de barras")
        refresh = QPushButton("Pesquisar  [Enter]"); refresh.clicked.connect(self.reload)
        search_row.addWidget(self.search, 1); search_row.addWidget(refresh); root.addLayout(search_row)
        self.table = QTableWidget(0, 7); self.table.setHorizontalHeaderLabels(
            ("Código", "Nome / descrição", "Preço", "Estoque", "Mínimo", "Tipo", "Situação")
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(42); self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader(); header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3): header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.installEventFilter(self); self.table.doubleClicked.connect(self.edit_product)
        root.addWidget(self.table, 1)
        buttons = QHBoxLayout(); self.new = QPushButton("Novo  [F3]"); self.edit = QPushButton("Editar  [F4]")
        self.xml_import = QPushButton("Preparar por XML  [F8]")
        self.move = QPushButton("Movimentar estoque  [F6]"); self.history = QPushButton("Histórico  [F7]")
        close = QPushButton("Fechar  [Esc]"); self.new.setObjectName("primary"); self.move.setObjectName("warning")
        self.new.clicked.connect(self.new_product); self.edit.clicked.connect(self.edit_product)
        self.xml_import.clicked.connect(self.open_xml_import)
        self.move.clicked.connect(self.move_stock); self.history.clicked.connect(self.show_history); close.clicked.connect(self.reject)
        for button in (self.new, self.edit, self.xml_import, self.move, self.history): buttons.addWidget(button)
        buttons.addStretch(); buttons.addWidget(close); root.addLayout(buttons)
        self._shortcuts = []
        for key, callback in (("F3", self.new_product), ("F4", self.edit_product), ("F5", self.reload),
                              ("F6", self.move_stock), ("F7", self.show_history),
                              ("F8", self.open_xml_import), ("Esc", self.reject)):
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

    def open_xml_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar XML local para preparar produtos", "", "XML (*.xml)",
        )
        if not path:
            return
        try:
            if self.application.nfe_purchase_import is not None:
                draft = self.application.prepare_purchase_xml(path)
                dialog = NFePurchaseImportDialog(
                    self.application.nfe_purchase_import, draft, self,
                )
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.reload()
                return
            draft = self.application.prepare_xml(path)
        except Exception as error:
            QMessageBox.warning(self, "XML não preparado", str(error))
            return
        dialog = ProductXMLReviewDialog(self.application, draft, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            created = len(dialog.result_data.created_product_ids)
            QMessageBox.information(
                self, "Cadastros concluídos",
                f"{created} produto(s) cadastrado(s) com estoque zero. IDs reais: "
                + (", ".join(map(str, dialog.result_data.created_product_ids)) or "nenhum"),
            )
            self.reload()
