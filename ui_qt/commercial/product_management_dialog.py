from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QFileDialog, QGroupBox, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
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
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.resize(1180, 760); self.setMinimumSize(900, 620); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); body_root = QVBoxLayout(body)
        commercial = QGroupBox("DADOS COMERCIAIS E ESTOQUE"); form = QFormLayout(commercial)
        self.code = QLineEdit(product.code if product else "")
        self.barcode = QLineEdit(product.barcode if product else "")
        existing_codes = tuple(getattr(product, "barcodes", ()) or ()) if product else ()
        self.additional_barcodes = QLineEdit("; ".join(existing_codes[1:]))
        self.additional_barcodes.setPlaceholderText("Um ou mais códigos separados por ponto e vírgula")
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
        self.unit = QComboBox()
        try:
            units = tuple(application.units())
        except Exception:
            units = ()
        if not units:
            units = ({"nome": "UN", "descricao": "Unidade", "permite_fracionado": 0},)
        for item in units:
            code = str(item.get("sigla") or item.get("nome") or "UN").upper()
            self.unit.addItem(f"{code} — {item.get('descricao') or code}", code)
        wanted_unit = str(getattr(product, "unit_code", "UN") or "UN").upper()
        for index in range(self.unit.count()):
            if self.unit.itemData(index) == wanted_unit:
                self.unit.setCurrentIndex(index); break
        self.fraction_policy = QComboBox()
        self.fraction_policy.addItem("Usar padrão da unidade", None)
        self.fraction_policy.addItem("Permitir venda fracionada", True)
        self.fraction_policy.addItem("Exigir quantidade inteira", False)
        if product:
            self.fraction_policy.setCurrentIndex(1 if product.allows_fractional_quantity else 2)
        if product:
            self.current_stock.setEnabled(False)
            self.current_stock.setToolTip("Use Movimentar estoque para alterar o saldo.")
        for label, widget in (
            ("Código", self.code), ("Código principal", self.barcode),
            ("Códigos adicionais", self.additional_barcodes),
            ("Nome / descrição*", self.description), ("Tipo", self.product_type),
            ("Unidade de venda", self.unit), ("Venda fracionada", self.fraction_policy),
            ("Preço de venda", self.sale_price), ("Preço de custo", self.cost_price),
            ("Estoque inicial" if not product else "Estoque atual", self.current_stock),
            ("Estoque mínimo", self.minimum_stock), ("", self.allow_negative),
        ): form.addRow(label, widget)
        body_root.addWidget(commercial)
        fiscal = QGroupBox("FICHA FISCAL DE VENDA — confirme com seu contador")
        fiscal_form = QFormLayout(fiscal)
        self.fiscal_status = QLabel("")
        self.fiscal_status.setWordWrap(True)
        self.fiscal_status.setStyleSheet("background:#2d2108;color:#ffd866;padding:10px;font-weight:800")
        fiscal_form.addRow(self.fiscal_status)
        self.ncm = QLineEdit(getattr(product, "ncm", "") if product else "")
        self.ncm_search = QPushButton("Pesquisar NCM oficial")
        ncm_row = QWidget(); ncm_layout = QHBoxLayout(ncm_row); ncm_layout.setContentsMargins(0,0,0,0)
        ncm_layout.addWidget(self.ncm, 1); ncm_layout.addWidget(self.ncm_search)
        self.cest = QLineEdit(getattr(product, "cest", "") if product else "")
        self.cest_search = QPushButton("Pesquisar CEST oficial")
        cest_row = QWidget(); cest_layout = QHBoxLayout(cest_row); cest_layout.setContentsMargins(0,0,0,0)
        cest_layout.addWidget(self.cest, 1); cest_layout.addWidget(self.cest_search)
        self.cfop = QLineEdit(getattr(product, "cfop", "") if product else "")
        self.cfop.setPlaceholderText("CFOP de saída/venda; não copie o CFOP de compra do XML")
        self.origin = QComboBox(); self.origin.addItem("Selecione…", "")
        for code, name in (("0","Nacional"),("1","Estrangeira — importação direta"),("2","Estrangeira — mercado interno"),("3","Nacional, conteúdo importação >40%"),("4","Nacional conforme processos básicos"),("5","Nacional, conteúdo importação ≤40%"),("6","Estrangeira sem similar nacional"),("7","Estrangeira mercado interno sem similar"),("8","Nacional, conteúdo importação >70%")):
            self.origin.addItem(f"{code} — {name}", code)
        self._select_data(self.origin, getattr(product, "fiscal_origin", "") if product else "")
        self.csosn = self._code_combo(("102","103","201","202","203","300","400","500"), getattr(product, "fiscal_csosn", "") if product else "")
        self.icms_cst = self._code_combo(("00","40","41","50","60"), getattr(product, "fiscal_icms_cst", "") if product else "")
        contribution = ("01","02","04","05","06","07","08","09","49","50","51","52","53","54","55","56","60","61","62","63","64","65","66","67","70","71","72","73","74","75","98","99")
        self.pis_cst = self._code_combo(contribution, getattr(product, "fiscal_pis_cst", "") if product else "")
        self.cofins_cst = self._code_combo(contribution, getattr(product, "fiscal_cofins_cst", "") if product else "")
        self.icms_rate = QLineEdit(str(getattr(product, "fiscal_icms_rate", 0) if product else 0))
        self.pis_rate = QLineEdit(str(getattr(product, "fiscal_pis_rate", 0) if product else 0))
        self.cofins_rate = QLineEdit(str(getattr(product, "fiscal_cofins_rate", 0) if product else 0))
        for label, widget in (("NCM*", ncm_row),("CEST (quando aplicável)", cest_row),("CFOP de venda*",self.cfop),("Origem da mercadoria*",self.origin),("CSOSN — Simples/MEI",self.csosn),("CST ICMS — regime normal",self.icms_cst),("Alíquota ICMS %",self.icms_rate),("CST PIS*",self.pis_cst),("Alíquota PIS %",self.pis_rate),("CST COFINS*",self.cofins_cst),("Alíquota COFINS %",self.cofins_rate)):
            fiscal_form.addRow(label, widget)
        body_root.addWidget(fiscal); body_root.addStretch(); scroll.setWidget(body); root.addWidget(scroll, 1)
        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton("Cancelar  [Esc]"); self.save = QPushButton("Salvar  [Enter]")
        self.save.setObjectName("primary"); cancel.clicked.connect(self.reject)
        self.save.clicked.connect(self._save); row.addWidget(cancel); row.addWidget(self.save)
        root.addLayout(row)
        self._fields = (
            self.code, self.barcode, self.additional_barcodes, self.description, self.product_type,
            self.unit, self.fraction_policy,
            self.sale_price, self.cost_price, self.current_stock,
            self.minimum_stock, self.allow_negative, self.ncm, self.ncm_search, self.cest,
            self.cest_search, self.cfop, self.origin, self.csosn, self.icms_cst,
            self.icms_rate, self.pis_cst, self.pis_rate, self.cofins_cst,
            self.cofins_rate, self.save,
        )
        for field in self._fields: field.installEventFilter(self)
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.setAutoRepeat(False); self._escape.activated.connect(self.reject)
        self.description.setFocus(Qt.FocusReason.OtherFocusReason)
        self.ncm_search.clicked.connect(lambda _checked=False: self._choose_catalog("NCM"))
        self.cest_search.clicked.connect(lambda _checked=False: self._choose_catalog("CEST"))
        self._refresh_fiscal_status()

    @staticmethod
    def _select_data(combo, value):
        for index in range(combo.count()):
            if str(combo.itemData(index) or "") == str(value or ""):
                combo.setCurrentIndex(index); return

    @classmethod
    def _code_combo(cls, values, selected):
        combo = QComboBox(); combo.addItem("Selecione…", "")
        for value in values: combo.addItem(value, value)
        cls._select_data(combo, selected); return combo

    def _refresh_fiscal_status(self):
        if not self.product or not hasattr(self.application, "fiscal_issues"):
            self.fiscal_status.setText("Preencha somente dados fiscais confirmados. O NabiCode não inventa tributação.")
            return
        try: issues = tuple(self.application.fiscal_issues(self.product.product_id))
        except Exception as error: self.fiscal_status.setText(f"Diagnóstico fiscal indisponível: {error}"); return
        self.fiscal_status.setText(
            "Ficha fiscal pronta para o pré-voo." if not issues else
            "Pendência que bloqueia o pré-voo: " + " | ".join(issue.message for issue in issues)
        )

    def _choose_catalog(self, kind):
        dialog = FiscalCatalogSearchDialog(self.application, kind, ncm=self.ncm.text(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_code: return
        (self.ncm if kind == "NCM" else self.cest).setText(dialog.selected_code)

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
            unit_code=str(self.unit.currentData() or "UN"),
            barcodes=tuple(
                code.strip() for code in self.additional_barcodes.text().split(";") if code.strip()
            ),
            allow_fractional_quantity=self.fraction_policy.currentData(),
            ncm=self.ncm.text().strip(), cest=self.cest.text().strip(),
            cfop=self.cfop.text().strip(), fiscal_origin=str(self.origin.currentData() or ""),
            fiscal_csosn=str(self.csosn.currentData() or ""),
            fiscal_icms_cst=str(self.icms_cst.currentData() or ""),
            fiscal_icms_rate=_decimal(self.icms_rate.text(), "Alíquota ICMS"),
            fiscal_pis_cst=str(self.pis_cst.currentData() or ""),
            fiscal_pis_rate=_decimal(self.pis_rate.text(), "Alíquota PIS"),
            fiscal_cofins_cst=str(self.cofins_cst.currentData() or ""),
            fiscal_cofins_rate=_decimal(self.cofins_rate.text(), "Alíquota COFINS"),
            fiscal_profile_source="MANUAL",
        )
        return ProductUpdateCommand(**values, product_id=self.product.product_id) if self.product else ProductCreateCommand(**values)

    def _save(self) -> None:
        try:
            command = self._command()
            self.saved = self.application.update(command) if self.product else self.application.create(command)
        except Exception as error:
            QMessageBox.warning(self, "Produtos", str(error)); self.description.setFocus(); return
        self.accept()


class FiscalCatalogSearchDialog(QDialog):
    def __init__(self, application, kind: str, *, ncm="", parent=None):
        super().__init__(parent); self.application=application; self.kind=kind; self.ncm=ncm; self.selected_code=""
        self.setWindowTitle(f"Pesquisar {kind} oficial"); self.resize(1050, 680); self.setStyleSheet(STYLE)
        root=QVBoxLayout(self); root.addWidget(QLabel(f"CATÁLOGO {kind} — referência oficial offline"))
        self.query=QLineEdit(); self.query.setPlaceholderText("Digite código ou descrição (mínimo 2 caracteres)")
        self.search_button=QPushButton("Pesquisar  [Enter]"); row=QHBoxLayout(); row.addWidget(self.query,1); row.addWidget(self.search_button); root.addLayout(row)
        self.table=QTableWidget(0,2); self.table.setHorizontalHeaderLabels((kind,"Descrição")); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch); root.addWidget(self.table,1)
        self.select=QPushButton("Selecionar  [Enter]"); self.select.setObjectName("primary"); root.addWidget(self.select)
        self.search_button.clicked.connect(self._search); self.select.clicked.connect(self._accept); self.table.cellDoubleClicked.connect(lambda *_: self._accept())
        QShortcut(QKeySequence("Esc"),self,activated=self.reject).setAutoRepeat(False); self.query.returnPressed.connect(self._search); self.table.installEventFilter(self); self.query.setFocus()

    def _search(self):
        try:
            entries=(self.application.search_ncm(self.query.text()) if self.kind=="NCM" else self.application.search_cest(self.query.text(),ncm=self.ncm))
        except Exception as error: QMessageBox.warning(self,f"Catálogo {self.kind}",str(error)); return
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values=(entry.code, entry.description)
            for column,value in enumerate(values): self.table.setItem(row,column,QTableWidgetItem(str(value)))
        if entries: self.table.selectRow(0); self.table.setFocus()

    def _accept(self):
        row=self.table.currentRow()
        if row<0: return
        self.selected_code=self.table.item(row,0).text(); self.accept()

    def eventFilter(self, watched, event):
        if watched is self.table and event.type()==QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            event.accept()
            if not event.isAutoRepeat(): self._accept()
            return True
        return super().eventFilter(watched,event)


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
        self.pending_xml = QPushButton("Notas pendentes")
        self.move = QPushButton("Movimentar estoque  [F11]"); self.history = QPushButton("Histórico  [F7]")
        close = QPushButton("Fechar  [Esc]"); self.new.setObjectName("primary"); self.move.setObjectName("warning")
        self.new.clicked.connect(self.new_product); self.edit.clicked.connect(self.edit_product)
        self.xml_import.clicked.connect(self.open_xml_import)
        self.pending_xml.clicked.connect(self.open_pending_xml)
        self.move.clicked.connect(self.move_stock); self.history.clicked.connect(self.show_history); close.clicked.connect(self.reject)
        for button in (self.new, self.edit, self.xml_import, self.pending_xml, self.move, self.history): buttons.addWidget(button)
        buttons.addStretch(); buttons.addWidget(close); root.addLayout(buttons)
        self._shortcuts = []
        for key, callback in (("F3", self.new_product), ("F4", self.edit_product), ("F5", self.reload),
                              ("F11", self.move_stock), ("F7", self.show_history),
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

    def open_pending_xml(self) -> None:
        service = getattr(self.application, "nfe_purchase_import", None)
        if service is None:
            QMessageBox.information(self, "Notas pendentes", "A entrada completa por NF-e não está disponível nesta edição.")
            return
        try: pending = tuple(service.pending_drafts())
        except Exception as error: QMessageBox.warning(self, "Notas pendentes", str(error)); return
        if not pending:
            QMessageBox.information(self, "Notas pendentes", "Não há notas aguardando finalização para este usuário e esta empresa.")
            return
        chooser = QDialog(self); chooser.setWindowTitle("Notas que precisam ser finalizadas"); chooser.resize(900, 480); chooser.setStyleSheet(STYLE)
        layout = QVBoxLayout(chooser); table = QTableWidget(len(pending), 5)
        table.setHorizontalHeaderLabels(("NF-e", "Fornecedor", "CNPJ", "Última edição", "Arquivo")); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for index, item in enumerate(pending):
            for column, value in enumerate((item["numero"], item["fornecedor_nome"], item["fornecedor_documento"], item["atualizado_em"], item["arquivo_origem"])):
                cell=QTableWidgetItem(str(value)); cell.setToolTip(str(value)); table.setItem(index,column,cell)
        table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch); table.selectRow(0); layout.addWidget(table)
        actions=QHBoxLayout(); discard=QPushButton("Descartar selecionada"); resume=QPushButton("Continuar selecionada"); resume.setObjectName("primary"); actions.addWidget(discard); actions.addStretch(); actions.addWidget(resume); layout.addLayout(actions)
        def selected():
            row=table.currentRow(); return pending[row] if 0 <= row < len(pending) else None
        def do_discard():
            item=selected()
            if not item: return
            answer=QMessageBox.question(chooser,"Descartar rascunho",f"Descartar definitivamente as edições da NF-e {item['numero']}?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes: return
            try: service.discard_draft(item["id"],confirmed=True)
            except Exception as error: QMessageBox.warning(chooser,"Rascunho preservado",str(error)); return
            chooser.reject()
        def do_resume():
            item=selected()
            if not item: return
            try: draft,state=service.resume_draft(item["id"])
            except Exception as error: QMessageBox.warning(chooser,"Não foi possível retomar",str(error)); return
            chooser.accept(); dialog=NFePurchaseImportDialog(service,draft,self,restored_state=state)
            if dialog.exec() == QDialog.DialogCode.Accepted: self.reload()
        discard.clicked.connect(do_discard); resume.clicked.connect(do_resume); table.doubleClicked.connect(lambda _index: do_resume()); chooser.exec()
