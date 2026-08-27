from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from administration.nfe_purchase_import_service import suggest_purchase_factor


WHITE_TABLE = """
QTableWidget{background:#ffffff;color:#111827;alternate-background-color:#21262d;
 border:1px solid #cbd5e1;gridline-color:#d1d5db;selection-background-color:#bfdbfe;
 selection-color:#111827} QHeaderView::section{background:#e5e7eb;color:#111827;
 padding:7px;border:0;border-right:1px solid #cbd5e1;font-weight:800}
QTableWidget::item:alternate{background:#21262d;color:#ffffff}
QTableWidget QLineEdit{background:#ffffff;color:#111827;border:1px solid #64748b}
"""


def _decimal(text, field, *, positive=False):
    try:
        value = Decimal(str(text or "").strip().replace(".", "").replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} inválido.") from exc
    if not value.is_finite() or value < 0 or (positive and value <= 0):
        raise ValueError(f"{field} inválido.")
    return value


def _number(value, places=4):
    result = f"{Decimal(str(value)):.{places}f}".rstrip("0").rstrip(".")
    return result.replace(".", ",") or "0"


class NFePurchaseImportDialog(QDialog):
    """Conferência humana de entrada; nada persiste antes da confirmação final."""

    def __init__(self, application, draft, parent=None, *, restored_state=None):
        super().__init__(parent)
        self.application = application
        self.draft = draft
        self.document = application.document(draft.draft_id)
        self.result_data = None
        self._busy = False
        self._loading = False
        self._columns_fitted = False
        self._price_columns_fitted = False
        self._editor_row = -1
        self._rows = []
        self.setWindowTitle("Importar NF-e de compra por XML")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint |
                            Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.resize(1440, 820); self.setMinimumSize(1120, 680)
        self.setStyleSheet("QDialog{background:#0d1117;color:#f0f6fc;font-size:13px} QLabel{color:#f0f6fc} "
                           "QLineEdit,QComboBox{min-height:34px;background:#161b22;color:#f0f6fc;border:1px solid #475569;padding:0 7px} "
                           "QPushButton{min-height:38px;background:#30363d;color:white;border:0;border-radius:5px;padding:0 12px;font-weight:800} "
                           "QPushButton#primary{background:#238636}")
        root = QVBoxLayout(self)
        root.addWidget(QLabel("IMPORTAÇÃO DE NF-e DE COMPRA — CONFERÊNCIA E ENTRADA"))
        evidence = QLabel(
            f"NF-e {draft.number or '—'} • Fornecedor: {draft.supplier_name} • "
            f"CNPJ: {draft.supplier_document} • Total: R$ {draft.document_total}"
        )
        evidence.setTextFormat(Qt.TextFormat.PlainText); root.addWidget(evidence)
        warning = QLabel(
            "O XML é evidência local. Vínculos exatos já comprovados são aplicados automaticamente; "
            "resultado ambíguo nunca é escolhido pelo sistema. Use Desvincular somente para corrigir "
            "uma associação indevida. A entrada ocorrerá somente na confirmação final."
        )
        warning.setWordWrap(True); warning.setStyleSheet("background:#2b2111;border-left:5px solid #d29922;padding:8px")
        root.addWidget(warning)
        self.pages = QStackedWidget(); root.addWidget(self.pages, 1)
        self._build_review_page(); self._build_price_page()
        self._build_confirmation_page(); self._build_completion_page()
        self._initialize_rows(); self._render_rows()
        if restored_state:
            self._restore_state(restored_state)
        self._connect_autosave()
        self._checkpoint()
        QShortcut(QKeySequence("Esc"), self, activated=self.reject).setAutoRepeat(False)

    def _restore_state(self, state):
        saved_rows = tuple(state.get("rows") or ())
        if len(saved_rows) != len(self._rows):
            raise ValueError("O rascunho não corresponde aos itens deste XML.")
        for index, saved in enumerate(saved_rows):
            row = self._rows[index]
            for key in ("acao", "produto_id", "codigo", "descricao", "codigo_barras", "tipo_fator", "fator", "unidade", "status"):
                if key in saved: row[key] = saved[key]
            row["margem"] = Decimal(str(saved.get("margem", row["margem"])))
            row["raw_margin"] = str(saved.get("raw_margin", _number(row["margem"], 2)))
            row["saved_ok"] = True; self._recalculate(index)
            # Margem e preço são um único cálculo. A margem restaurada recompõe
            # o preço e corrige rascunhos antigos exibidos indevidamente como 0.
            row["raw_price"] = _number(row["preco"], 2)
        self._render_rows()
        page = max(0, min(int(state.get("page", 0)), 2))
        if page >= 1: self._render_prices()
        if page == 2: self._show_confirmation()
        else: self.pages.setCurrentIndex(page)

    def _connect_autosave(self):
        for field in (self.name, self.barcode, self.factor, self.bulk_margin):
            field.textChanged.connect(self._checkpoint)
        for field in (self.factor_kind, self.stock_unit):
            field.currentIndexChanged.connect(self._checkpoint)
        self.pages.currentChanged.connect(self._checkpoint)

    def _checkpoint(self, *_args, capture_current=True):
        if self._loading or self._busy or not hasattr(self.application, "save_draft"):
            return
        index = self._editor_row
        if capture_current and index >= 0:
            row = self._rows[index]
            row["descricao"] = self.name.text()
            row["codigo_barras"] = self.barcode.text()
            row["tipo_fator"] = self.factor_kind.currentData() or row["tipo_fator"]
            row["fator"] = self.factor.text().strip().replace(",", ".") or row["fator"]
            row["unidade"] = self.stock_unit.currentData() or row["unidade"]
        if hasattr(self, "price_table"):
            for row_index, row in enumerate(self._rows):
                margin = self.price_table.cellWidget(row_index, 3)
                price = self.price_table.cellWidget(row_index, 4)
                if margin is not None: row["raw_margin"] = margin.text()
                if price is not None: row["raw_price"] = price.text()
        try:
            self.application.save_draft(self.draft, tuple(self._rows), page=self.pages.currentIndex())
        except Exception as error:
            self.checkpoint_status.setText(f"Rascunho NÃO salvo: {error}")
            self.checkpoint_status.setStyleSheet("color:#ef4444;font-weight:800")
            return
        self.checkpoint_status.setText("Rascunho salvo automaticamente")
        self.checkpoint_status.setStyleSheet("color:#16a34a;font-weight:800")

    def _build_review_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        tools = QHBoxLayout(); tools.addWidget(QLabel("Visualização"))
        self.review_view_mode = QComboBox(); self.review_view_mode.addItem("Detalhes", "DETAILS"); self.review_view_mode.addItem("Compacto", "COMPACT")
        self.review_font_size = QComboBox()
        for size in (11, 12, 13, 14, 16, 18): self.review_font_size.addItem(f"Fonte {size}", size)
        self.review_font_size.setCurrentIndex(self.review_font_size.findData(13))
        self.review_view_mode.currentIndexChanged.connect(self._apply_review_view)
        self.review_font_size.currentIndexChanged.connect(self._apply_review_view)
        self.checkpoint_status = QLabel("Rascunho ainda não salvo")
        tools.addWidget(self.review_view_mode); tools.addWidget(self.review_font_size); tools.addStretch()
        tools.addWidget(self.checkpoint_status); layout.addLayout(tools)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels((
            "Código", "Nome do produto", "CFOP", "Qtd. compra", "Un. XML",
            "Fator", "Un. estoque", "Qtd. estoque", "Custo unitário", "Vínculo",
        ))
        self.table.setStyleSheet(WHITE_TABLE); self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(30)
        header = self.table.horizontalHeader(); header.setStretchLastSection(False)
        header.setSectionsMovable(True); header.setMinimumSectionSize(45)
        for column in range(self.table.columnCount()):
            header.setSectionResizeMode(column, header.ResizeMode.Interactive)
        header.resizeSection(0, 90); header.resizeSection(1, 430); header.resizeSection(2, 65)
        header.resizeSection(3, 105); header.resizeSection(4, 75); header.resizeSection(5, 75)
        header.resizeSection(6, 95); header.resizeSection(7, 105); header.resizeSection(8, 105)
        header.resizeSection(9, 130)
        self.table.currentCellChanged.connect(self._selection_changed)
        splitter.addWidget(self.table)
        details = QWidget(); details.setMinimumWidth(380); details.setMaximumWidth(440)
        form = QFormLayout(details); form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.status = QLabel(); self.status.setWordWrap(True)
        self.linked_product = QLabel(); self.linked_product.setWordWrap(True)
        self.name = QLineEdit(); self.barcode = QLineEdit()
        self.unlink = QPushButton("Desvincular e cadastrar como novo")
        self.unlink.clicked.connect(self._unlink_selected)
        self.restore_link = QPushButton("Desfazer desvínculo")
        self.restore_link.clicked.connect(self._restore_selected_link)
        self.factor_kind = QComboBox(); self.factor_kind.addItem("Multiplicar", "MULTIPLICAR")
        self.factor_kind.addItem("Dividir", "DIVIDIR")
        self.factor = QLineEdit("1"); self.suggest_factor = QPushButton("Nabi sugerir fator")
        self.suggest_factor.clicked.connect(self._suggest_factor); self.stock_unit = QComboBox()
        for code, description in self.application.units():
            self.stock_unit.addItem(f"{code} — {description}", code)
        self.conversion = QLabel(); self.save_item = QPushButton("Salvar edição deste item")
        self.save_item.setObjectName("primary")
        self.save_item.clicked.connect(lambda _checked=False: self._save_selected())
        for label, widget in (("Situação", self.status),
                              ("Nome do produto", self.name), ("Vínculo", self.linked_product),
                              ("", self.unlink),
                              ("", self.restore_link),
                              ("Código de barras", self.barcode), ("Tipo de fator", self.factor_kind),
                              ("Fator informado", self.factor), ("", self.suggest_factor),
                              ("Unidade de venda", self.stock_unit),
                              ("Resultado", self.conversion), ("", self.save_item)):
            form.addRow(label, widget)
        self.factor.textEdited.connect(self._preview_conversion)
        self.factor_kind.currentIndexChanged.connect(self._preview_conversion)
        splitter.addWidget(details); splitter.setSizes((1050, 390)); layout.addWidget(splitter, 1)
        nav = QHBoxLayout(); cancel = QPushButton("Cancelar [Esc]"); self.to_prices = QPushButton("Avançar para preços")
        self.to_prices.setObjectName("primary"); cancel.clicked.connect(self.reject); self.to_prices.clicked.connect(self._show_prices)
        nav.addStretch(); nav.addWidget(cancel); nav.addWidget(self.to_prices); layout.addLayout(nav)
        self.pages.addWidget(page)

    def _build_price_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        line = QHBoxLayout(); line.addWidget(QLabel("Margem para todos (%)")); self.bulk_margin = QLineEdit("0")
        apply_all = QPushButton("Aplicar a todos"); apply_all.clicked.connect(self._apply_bulk_margin)
        self.bulk_margin.textEdited.connect(self._bulk_margin_changed)
        line.addWidget(self.bulk_margin); line.addWidget(apply_all); line.addStretch()
        line.addWidget(QLabel("Visualização")); self.price_view_mode = QComboBox(); self.price_view_mode.addItem("Detalhes", "DETAILS"); self.price_view_mode.addItem("Compacto", "COMPACT")
        self.price_font_size = QComboBox()
        for size in (11, 12, 13, 14, 16, 18): self.price_font_size.addItem(f"Fonte {size}", size)
        self.price_font_size.setCurrentIndex(self.price_font_size.findData(13))
        self.price_view_mode.currentIndexChanged.connect(self._apply_price_view); self.price_font_size.currentIndexChanged.connect(self._apply_price_view)
        line.addWidget(self.price_view_mode); line.addWidget(self.price_font_size); layout.addLayout(line)
        price_help = QLabel(
            "A margem é aplicada imediatamente: 0% deixa o preço igual ao custo. "
            "Você também pode informar diretamente o preço de venda em cada linha."
        )
        price_help.setWordWrap(True); price_help.setStyleSheet("color:#fbbf24;font-weight:800")
        layout.addWidget(price_help)
        self.price_table = QTableWidget(0, 6)
        self.price_table.setHorizontalHeaderLabels((
            "Item", "Produto", "Custo unitário", "Margem %", "Preço de venda", "Alerta",
        ))
        self.price_table.setStyleSheet(WHITE_TABLE); self.price_table.setAlternatingRowColors(True)
        self.price_table.verticalHeader().setVisible(False); self.price_table.verticalHeader().setDefaultSectionSize(36)
        price_header = self.price_table.horizontalHeader(); price_header.setSectionsMovable(True); price_header.setStretchLastSection(False); price_header.setMinimumSectionSize(45)
        for column in range(self.price_table.columnCount()): price_header.setSectionResizeMode(column, price_header.ResizeMode.Interactive)
        layout.addWidget(self.price_table, 1)
        self.final_summary = QLabel(); self.final_summary.setWordWrap(True); layout.addWidget(self.final_summary)
        nav = QHBoxLayout(); self.back_to_items = QPushButton("Voltar sem perder alterações"); self.review = QPushButton("Revisar entrada")
        self.review.setObjectName("primary"); self.back_to_items.clicked.connect(lambda: self.pages.setCurrentIndex(0)); self.review.clicked.connect(self._show_confirmation)
        nav.addWidget(self.back_to_items); nav.addStretch(); nav.addWidget(self.review); layout.addLayout(nav)
        self.pages.addWidget(page)

    def _build_confirmation_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel("REVISÃO FINAL — NENHUM DADO FOI GRAVADO AINDA"))
        self.confirmation_supplier = QLabel(); self.confirmation_supplier.setWordWrap(True); layout.addWidget(self.confirmation_supplier)
        self.confirmation_table = QTableWidget(0, 8); self.confirmation_table.setHorizontalHeaderLabels((
            "Produto", "Ação", "Fator", "Conversão", "Unidade", "Custo", "Margem", "Preço",
        ))
        self.confirmation_table.setStyleSheet(WHITE_TABLE); self.confirmation_table.setAlternatingRowColors(True)
        self.confirmation_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.confirmation_table.verticalHeader().setVisible(False)
        confirmation_header = self.confirmation_table.horizontalHeader(); confirmation_header.setSectionsMovable(True); confirmation_header.setStretchLastSection(False)
        for column in range(self.confirmation_table.columnCount()): confirmation_header.setSectionResizeMode(column, confirmation_header.ResizeMode.Interactive)
        layout.addWidget(self.confirmation_table, 1)
        self.confirmation_notes = QLabel(); self.confirmation_notes.setWordWrap(True); layout.addWidget(self.confirmation_notes)
        self.confirmation_text = QTextEdit(); self.confirmation_text.setVisible(False); self.confirmation_text.setReadOnly(True)
        nav = QHBoxLayout(); self.back_to_prices = QPushButton("Voltar aos preços")
        self.confirm = QPushButton("Confirmar entrada da nota")
        self.confirm.setObjectName("primary"); self.back_to_prices.clicked.connect(lambda: self.pages.setCurrentIndex(1)); self.confirm.clicked.connect(self._commit)
        nav.addWidget(self.back_to_prices); nav.addStretch(); nav.addWidget(self.confirm); layout.addLayout(nav)
        self.pages.addWidget(page)

    def _build_completion_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel("IMPORTAÇÃO CONCLUÍDA"))
        self.completion_text = QTextEdit(); self.completion_text.setReadOnly(True)
        self.completion_text.setStyleSheet(
            "background:#ffffff;color:#111827;border:1px solid #cbd5e1;"
            "padding:16px;font-size:16px"
        )
        layout.addWidget(self.completion_text, 1)
        close = QPushButton("Fechar"); close.setObjectName("primary"); close.clicked.connect(self.accept)
        layout.addWidget(close); self.pages.addWidget(page)

    def _initialize_rows(self):
        for index, (draft_item, xml_item) in enumerate(zip(self.draft.items, self.document.itens)):
            saved = self.application.saved_link(self.draft, index)
            candidates = list(draft_item.candidates)
            product_id = int(saved["produto_id"]) if saved else draft_item.suggested_product_id
            status = "SALVO" if saved else "EXATO_NOVO" if draft_item.match_status == "VINCULAR" else draft_item.match_status
            factor = str(saved["fator_conversao"]) if saved else "1"
            unit = str(saved["unidade_estoque"]) if saved else "UN"
            action = "ATUALIZAR" if product_id else "CRIAR"
            self._rows.append({
                "acao": action, "produto_id": product_id, "codigo": draft_item.supplier_code,
                "descricao": draft_item.description, "codigo_barras": str(xml_item.codigo_barras or ""),
                "tipo_fator": "MULTIPLICAR", "fator": factor, "unidade": unit,
                "margem": Decimal("0"), "preco": Decimal("0"), "status": status,
                "raw_margin": "0", "raw_price": "0",
                "candidates": candidates, "saved": saved, "saved_ok": True,
                "unlinked_snapshot": None,
            })
            self._recalculate(index)
            self._rows[index]["raw_price"] = _number(self._rows[index]["preco"], 2)

    def _factor(self, row):
        entered = _decimal(row["fator"], "Fator", positive=True)
        return entered if row["tipo_fator"] == "MULTIPLICAR" else Decimal("1") / entered

    def _recalculate(self, index):
        row = self._rows[index]; xml_item = self.document.itens[index]
        factor = self._factor(row)
        row["stock_quantity"] = (Decimal(str(xml_item.quantidade)) * factor).quantize(Decimal("0.0001"))
        row["unit_cost"] = (Decimal(str(xml_item.valor_unitario)) / factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        row["preco"] = (row["unit_cost"] * (Decimal("1") + row["margem"] / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _render_rows(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._rows))
        for index in range(len(self._rows)):
            self._update_row_cells(index)
        if self.table.rowCount() and self.table.currentRow() < 0: self.table.selectRow(0)
        self.table.blockSignals(False)
        if not self._columns_fitted:
            self._fit_columns_to_content(); self._columns_fitted = True
        if self.table.currentRow() >= 0:
            self._load_selected()

    def _fit_columns_to_content(self):
        caps = (110, 360, 65, 95, 70, 70, 90, 95, 100, 120)
        minimums = (65, 210, 50, 75, 55, 55, 70, 75, 80, 85)
        for column, (minimum, maximum) in enumerate(zip(minimums, caps)):
            content = self.table.sizeHintForColumn(column) + 12
            self.table.setColumnWidth(column, max(minimum, min(content, maximum)))

    def _update_row_cells(self, index):
        row = self._rows[index]; item = self.document.itens[index]
        mark = "● SALVO" if row["status"] == "SALVO" else "● EXATO" if row["status"] == "EXATO_NOVO" else "⚠ REVISAR" if row["produto_id"] else "NOVO"
        values = (item.codigo, row["descricao"], item.cfop, _number(item.quantidade),
                  item.unidade, row["fator"], row["unidade"],
                  _number(row["stock_quantity"]), _number(row["unit_cost"], 2), mark)
        for column, value in enumerate(values):
            cell = QTableWidgetItem(str(value)); cell.setToolTip(str(value))
            if column == 9:
                cell.setForeground(QColor("#15803d" if row["status"] == "SALVO" else "#1d4ed8" if row["status"] == "EXATO_NOVO" else "#b45309"))
            self.table.setItem(index, column, cell)

    def _load_selected(self):
        index = self.table.currentRow()
        if index < 0: return
        self._loading = True; self._editor_row = index; row = self._rows[index]
        labels = {"SALVO": "Vínculo anterior confirmado", "EXATO_NOVO": "Coincidência exata nova — revisar", "REVISAR": "Sem vínculo exato — escolha humana", "NOVO": "Produto novo"}
        self.status.setText(labels.get(row["status"], row["status"]))
        product_name = ""
        if row["saved"] and row["produto_id"] == int(row["saved"]["produto_id"]):
            product_name = str(row["saved"]["nome"])
        if not product_name:
            product_name = next((str(candidate.description) for candidate in row["candidates"] if candidate.product_id == row["produto_id"]), "")
        self.linked_product.setText(
            f"Vinculado automaticamente ao produto {product_name} (ID {row['produto_id']})"
            if row["produto_id"] else "Sem vínculo: será cadastrado como produto novo"
        )
        self.unlink.setEnabled(bool(row["produto_id"]))
        self.restore_link.setEnabled(row.get("unlinked_snapshot") is not None)
        self.name.setText(row["descricao"]); self.barcode.setText(row["codigo_barras"])
        self.factor_kind.setCurrentIndex(max(0, self.factor_kind.findData(row["tipo_fator"])))
        self.factor.setText(str(row["fator"]).replace(".", ",")); self.stock_unit.setCurrentIndex(max(0, self.stock_unit.findData(row["unidade"])))
        self._loading = False; self._preview_conversion()

    def _selection_changed(self, current_row, _current_column, previous_row, _previous_column):
        if self._loading:
            return
        editor_row = self._editor_row
        if editor_row >= 0 and editor_row != current_row and not self._save_selected(editor_row, show_error=False):
            self._loading = True; self.table.selectRow(editor_row); self._loading = False
            QMessageBox.warning(self, "Revisar item", "Corrija o item atual antes de selecionar outro.")
            return
        self._load_selected()

    def _unlink_selected(self):
        index = self.table.currentRow()
        if index < 0:
            return
        row = self._rows[index]
        if row.get("unlinked_snapshot") is None:
            row["unlinked_snapshot"] = {key: row.get(key) for key in ("acao", "produto_id", "saved", "status", "saved_ok")}
        row.update({"acao": "CRIAR", "produto_id": None, "saved": None, "status": "NOVO", "saved_ok": True})
        self.table.blockSignals(True); self._update_row_cells(index); self.table.blockSignals(False)
        self._load_selected()
        self._checkpoint()

    def _restore_selected_link(self):
        index = self.table.currentRow()
        if index < 0: return
        row = self._rows[index]; snapshot = row.get("unlinked_snapshot")
        if snapshot is None: return
        row.update(snapshot); row["unlinked_snapshot"] = None
        self.table.blockSignals(True); self._update_row_cells(index); self.table.blockSignals(False)
        self._load_selected()
        self._checkpoint()

    def _apply_review_view(self):
        if not hasattr(self, "table"): return
        size = int(self.review_font_size.currentData() or 13); self.table.setStyleSheet(WHITE_TABLE + f"QTableWidget{{font-size:{size}px}}")
        compact = self.review_view_mode.currentData() == "COMPACT"
        self.table.verticalHeader().setDefaultSectionSize(max(24, size + (11 if compact else 19)))

    def _apply_price_view(self):
        if not hasattr(self, "price_table"): return
        size = int(self.price_font_size.currentData() or 13); self.price_table.setStyleSheet(WHITE_TABLE + f"QTableWidget{{font-size:{size}px}} QLineEdit{{font-size:{size}px}}")
        compact = self.price_view_mode.currentData() == "COMPACT"
        self.price_table.verticalHeader().setDefaultSectionSize(max(26, size + (12 if compact else 23)))

    def _preview_conversion(self):
        if self._loading or self.table.currentRow() < 0: return
        try:
            entered = _decimal(self.factor.text(), "Fator", positive=True)
            factor = entered if self.factor_kind.currentData() == "MULTIPLICAR" else Decimal("1") / entered
            qty = Decimal(str(self.document.itens[self.table.currentRow()].quantidade)) * factor
            self.conversion.setText(f"{_number(qty)} {self.stock_unit.currentData() or 'UN'} entrarão no estoque")
        except ValueError:
            self.conversion.setText("Informe um fator positivo")

    def _suggest_factor(self):
        suggestion = suggest_purchase_factor(self.name.text())
        if suggestion is None:
            QMessageBox.information(
                self, "Sugestão da Nabi",
                "Não encontrei no nome uma quantidade de embalagem explícita e segura. "
                "Confira a embalagem e informe o fator manualmente.",
            )
            return
        answer = QMessageBox.question(
            self, "Sugestão da Nabi",
            f"O nome informa “{suggestion.evidence}”.\n\n"
            f"Sugestão: multiplicar por {_number(suggestion.factor)}.\n"
            "Deseja preencher esse fator para você revisar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.factor_kind.setCurrentIndex(self.factor_kind.findData("MULTIPLICAR"))
        self.factor.setText(_number(suggestion.factor))
        self._preview_conversion()

    def _save_selected(self, index=None, *, show_error=True):
        index = self._editor_row if index is None else index
        if index < 0: return False
        try:
            factor = _decimal(self.factor.text(), "Fator", positive=True)
            row = self._rows[index]; action = row["acao"]; product_id = row["produto_id"]
            if not self.name.text().strip(): raise ValueError("A descrição de venda é obrigatória.")
            if self.stock_unit.currentData() is None: raise ValueError("Selecione uma unidade de estoque/venda.")
        except ValueError as error:
            if show_error: QMessageBox.warning(self, "Revisar item", str(error))
            return False
        row.update({
            "acao": action, "produto_id": product_id, "descricao": self.name.text().strip(),
            "codigo_barras": self.barcode.text().strip(), "tipo_fator": self.factor_kind.currentData(),
            "fator": format(factor, "f"), "unidade": self.stock_unit.currentData(), "saved_ok": True,
        })
        self._recalculate(index)
        self.table.blockSignals(True); self._update_row_cells(index); self.table.blockSignals(False)
        # A mudança de seleção já aponta currentRow() para a próxima linha.
        # Não recapture os widgets aqui: eles ainda pertencem à linha salva.
        self._checkpoint(capture_current=False)
        return True

    def _duplicate_barcodes(self):
        occurrences = {}
        for index, row in enumerate(self._rows, start=1):
            barcode = str(row.get("codigo_barras") or "").strip()
            if barcode:
                identity = (
                    ("produto", int(row["produto_id"]))
                    if row.get("produto_id") is not None
                    else (
                        "novo",
                        " ".join(str(row.get("descricao") or "").casefold().split()),
                        str(row.get("unidade") or "").upper(),
                    )
                )
                occurrences.setdefault(barcode, []).append((index, identity))
        return {
            barcode: tuple(index for index, _identity in entries)
            for barcode, entries in occurrences.items()
            if len({identity for _index, identity in entries}) > 1
        }

    def _validate_unique_barcodes(self):
        duplicates = self._duplicate_barcodes()
        if not duplicates:
            return True
        details = "; ".join(
            f"{barcode} nas linhas {', '.join(map(str, lines))}"
            for barcode, lines in duplicates.items()
        )
        QMessageBox.warning(
            self,
            "Códigos de barras repetidos",
            "Corrija ou vincule os produtos antes de continuar. " + details,
        )
        self.pages.setCurrentIndex(0)
        self.table.selectRow(next(iter(duplicates.values()))[0] - 1)
        self.barcode.setFocus(Qt.FocusReason.OtherFocusReason)
        return False

    def _show_prices(self):
        try:
            if not self._save_selected():
                return
            if not self._validate_unique_barcodes():
                return
            for index, row in enumerate(self._rows):
                if not row.get("saved_ok"): raise ValueError(f"Revise e salve o item {index + 1}.")
                self._recalculate(index)
        except ValueError as error:
            QMessageBox.warning(self, "Revisar produtos", str(error)); return
        self._render_prices(); self.pages.setCurrentIndex(1)
        self._checkpoint()

    def _render_prices(self):
        self.price_table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            fixed = (index + 1, row["descricao"], _number(row["unit_cost"], 2))
            for column, value in enumerate(fixed):
                item = QTableWidgetItem(str(value))
                item.setForeground(QColor("#ffffff" if index % 2 else "#111827"))
                self.price_table.setItem(index, column, item)
            margin = QLineEdit(str(row.get("raw_margin", _number(row["margem"], 2))))
            price = QLineEdit(str(row.get("raw_price", _number(row["preco"], 2))))
            margin.textEdited.connect(lambda _text, i=index: self._margin_changed(i))
            price.textEdited.connect(lambda _text, i=index: self._price_changed(i))
            self.price_table.setCellWidget(index, 3, margin); self.price_table.setCellWidget(index, 4, price)
            alert = QTableWidgetItem(""); alert.setForeground(QColor("#991b1b"))
            self.price_table.setItem(index, 5, alert)
        if not self._price_columns_fitted:
            self._fit_price_columns(); self._price_columns_fitted = True
        self._refresh_summary()
        self._checkpoint()

    def _fit_price_columns(self):
        minimums = (50, 180, 85, 75, 95, 80); caps = (75, 460, 125, 105, 135, 260)
        for column, (minimum, maximum) in enumerate(zip(minimums, caps)):
            self.price_table.setColumnWidth(column, max(minimum, min(self.price_table.sizeHintForColumn(column) + 14, maximum)))

    def _margin_changed(self, index):
        if self._loading: return
        try:
            margin = _decimal(self.price_table.cellWidget(index, 3).text(), "Margem")
            self._rows[index]["margem"] = margin; self._rows[index]["raw_margin"] = self.price_table.cellWidget(index, 3).text(); self._recalculate(index)
            self._loading = True; self.price_table.cellWidget(index, 4).setText(_number(self._rows[index]["preco"], 2)); self._loading = False
            self.price_table.item(index, 5).setText("")
        except ValueError:
            self.price_table.item(index, 5).setText("Margem inválida")
        self._refresh_summary()
        self._checkpoint()

    def _price_changed(self, index):
        if self._loading: return
        try:
            price = _decimal(self.price_table.cellWidget(index, 4).text(), "Preço")
            cost = self._rows[index]["unit_cost"]
            margin = ((price / cost - 1) * 100).quantize(Decimal("0.01")) if cost else Decimal("0")
            if margin < 0: raise ValueError("Preço abaixo do custo")
            self._rows[index].update({"preco": price, "margem": margin, "raw_price": self.price_table.cellWidget(index, 4).text(), "raw_margin": _number(margin, 2)})
            self._loading = True; self.price_table.cellWidget(index, 3).setText(_number(margin, 2)); self._loading = False
            self.price_table.item(index, 5).setText("")
        except (ValueError, InvalidOperation, ZeroDivisionError) as error:
            self.price_table.item(index, 5).setText(str(error))
        self._refresh_summary()

    def _apply_bulk_margin(self):
        try: margin = _decimal(self.bulk_margin.text(), "Margem geral")
        except ValueError as error: QMessageBox.warning(self, "Ajustar preços", str(error)); return
        for index, row in enumerate(self._rows):
            row["margem"] = margin; row["raw_margin"] = _number(margin, 2); self._recalculate(index); row["raw_price"] = _number(row["preco"], 2)
        self._render_prices()
        self._checkpoint()

    def _bulk_margin_changed(self, _text):
        """Atualiza a grade enquanto o operador digita, sem exigir outro clique."""

        if self._loading or self.pages.currentIndex() != 1:
            return
        try:
            margin = _decimal(self.bulk_margin.text(), "Margem geral")
        except ValueError:
            return
        self._loading = True
        try:
            for index, row in enumerate(self._rows):
                row["margem"] = margin; row["raw_margin"] = _number(margin, 2)
                self._recalculate(index); row["raw_price"] = _number(row["preco"], 2)
                margin_edit = self.price_table.cellWidget(index, 3)
                price_edit = self.price_table.cellWidget(index, 4)
                if margin_edit is not None: margin_edit.setText(row["raw_margin"])
                if price_edit is not None: price_edit.setText(row["raw_price"])
                alert = self.price_table.item(index, 5)
                if alert is not None: alert.setText("")
        finally:
            self._loading = False
        self._refresh_summary(); self._checkpoint()

    def _refresh_summary(self):
        total = sum((row["stock_quantity"] for row in self._rows), Decimal("0"))
        self.final_summary.setText(
            f"{len(self._rows)} item(ns) • {_number(total)} unidade(s) de estoque convertidas. "
            "A forma/parcelas financeiras serão preservadas somente quando comprovadas no XML; "
            "nenhum contato com a SEFAZ ocorrerá nesta entrada."
        )

    def _show_confirmation(self):
        for index in range(len(self._rows)):
            self._margin_changed(index)
        if any(self.price_table.item(i, 5).text() for i in range(len(self._rows))):
            QMessageBox.warning(self, "Revisar preços", "Corrija os preços destacados antes de revisar.")
            return
        lines = [
            f"NF-e {self.draft.number or '—'} — {self.draft.supplier_name}",
            f"CNPJ do fornecedor: {self.draft.supplier_document}",
            f"Total comprovado no XML: R$ {self.draft.document_total}", "",
        ]
        for index, row in enumerate(self._rows, start=1):
            operation = "ATUALIZAR E VINCULAR" if row["produto_id"] else "CADASTRAR E VINCULAR"
            lines.append(
                f"{index}. {row['descricao']} — {operation} — fator {row['fator']} "
                f"({row['tipo_fator'].lower()}) — {_number(row['stock_quantity'])} {row['unidade']} no estoque — "
                f"custo R$ {_number(row['unit_cost'], 2)} — preço R$ {_number(row['preco'], 2)}"
            )
        duplicates = tuple(getattr(self.document, "duplicatas", ()) or ())
        lines.extend(("", f"Financeiro: {len(duplicates)} título(s) comprovado(s) no XML." if duplicates else
                      "Financeiro: nenhum título será inventado; o XML não contém duplicatas."))
        lines.append("Nenhuma comunicação com a SEFAZ será realizada nesta entrada local.")
        self.confirmation_text.setPlainText("\n".join(lines))
        self.confirmation_supplier.setText(
            f"Fornecedor: {self.draft.supplier_name} • CNPJ: {self.draft.supplier_document} • "
            f"NF-e {self.draft.number or '—'} • Total do XML: R$ {self.draft.document_total}"
        )
        self.confirmation_table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            action = "ATUALIZAR E VINCULAR" if row["produto_id"] else "CADASTRAR E VINCULAR"
            values = (row["descricao"], action, f"{row['tipo_fator'].lower()} {row['fator']}",
                      _number(row["stock_quantity"]), row["unidade"], f"R$ {_number(row['unit_cost'], 2)}",
                      f"{_number(row['margem'], 2)}%", f"R$ {_number(row['preco'], 2)}")
            for column, value in enumerate(values): self.confirmation_table.setItem(index, column, QTableWidgetItem(str(value)))
        confirmation_caps = (420, 190, 140, 110, 90, 110, 95, 110)
        for column, cap in enumerate(confirmation_caps): self.confirmation_table.setColumnWidth(column, min(self.confirmation_table.sizeHintForColumn(column) + 14, cap))
        self.confirmation_notes.setText(
            (f"Financeiro: {len(duplicates)} título(s) comprovado(s) no XML." if duplicates else
             "Financeiro: nenhum título será inventado; o XML não contém duplicatas.") +
            " Nenhuma comunicação com a SEFAZ será realizada nesta entrada local."
        )
        self.pages.setCurrentIndex(2)

    def _commit(self):
        if self._busy: return
        if not self._validate_unique_barcodes(): return
        answer = QMessageBox.question(
            self, "Confirmar entrada da NF-e",
            "Confirma os vínculos, cadastros, fatores, preços, entrada de estoque e financeiro?\n\n"
            "A operação é única e atômica: qualquer falha desfaz tudo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes: return
        self._busy = True; self.confirm.setEnabled(False)
        try:
            self.result_data = self.application.commit(self.draft, tuple(self._rows), confirmed=True)
        except Exception as error:
            self._busy = False; self.confirm.setEnabled(True)
            QMessageBox.warning(self, "Entrada não realizada", str(error)); return
        result = dict(self.result_data or {})
        products = tuple(result.get("resultados") or ())
        rows = "".join(
            "<tr>"
            f"<td>{escape(str(item.get('descricao') or '—'))}</td>"
            f"<td>{escape(str(item.get('status') or '—').upper())}</td>"
            f"<td style='text-align:right'>+{escape(str(item.get('quantidade_estoque') or 0))}</td>"
            "</tr>"
            for item in products
        )
        indication = escape(str(result.get("financeiro_indicacao") or "Nenhuma informação financeira."))
        html = f"""
        <h1 style='color:#15803d'>Entrada concluída com segurança</h1>
        <p style='font-size:18px'><b>Importação nº {escape(str(result.get('importacao_id', '—')))}</b></p>
        <table cellspacing='10' cellpadding='10' width='100%'>
          <tr>
            <td bgcolor='#dcfce7'><b>Produtos criados</b><br><span style='font-size:22px'>{result.get('itens_criados', 0)}</span></td>
            <td bgcolor='#dbeafe'><b>Vinculados/atualizados</b><br><span style='font-size:22px'>{result.get('itens_vinculados', 0)}</span></td>
            <td bgcolor='#fef3c7'><b>Títulos financeiros</b><br><span style='font-size:22px'>{len(result.get('titulo_ids') or ())}</span></td>
          </tr>
        </table>
        <h2>Resultado por produto</h2>
        <table border='1' cellspacing='0' cellpadding='8' width='100%' style='border-color:#cbd5e1'>
          <tr bgcolor='#e5e7eb'><th align='left'>Produto</th><th align='left'>Situação</th><th align='right'>Entrada no estoque</th></tr>
          {rows}
        </table>
        <h2>Financeiro</h2><p>{indication}</p>
        """
        self.completion_text.setHtml(html); self.pages.setCurrentIndex(3)
