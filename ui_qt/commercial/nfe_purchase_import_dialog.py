from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)


WHITE_TABLE = """
QTableWidget{background:#ffffff;color:#111827;alternate-background-color:#f3f4f6;
 border:1px solid #cbd5e1;gridline-color:#d1d5db;selection-background-color:#bfdbfe;
 selection-color:#111827} QHeaderView::section{background:#e5e7eb;color:#111827;
 padding:7px;border:0;border-right:1px solid #cbd5e1;font-weight:800}
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

    def __init__(self, application, draft, parent=None):
        super().__init__(parent)
        self.application = application
        self.draft = draft
        self.document = application.document(draft.draft_id)
        self.result_data = None
        self._busy = False
        self._loading = False
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
        QShortcut(QKeySequence("Esc"), self, activated=self.reject).setAutoRepeat(False)

    def _build_review_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels((
            "Vínculo", "Item", "Código", "Descrição", "CFOP", "Qtd. embalagens",
            "Un. XML", "Fator", "Un. estoque", "Qtd. estoque", "Custo unitário",
        ))
        self.table.setStyleSheet(WHITE_TABLE); self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(3, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.currentCellChanged.connect(self._selection_changed)
        splitter.addWidget(self.table)
        details = QWidget(); form = QFormLayout(details)
        self.status = QLabel(); self.linked_product = QLabel(); self.name = QLineEdit(); self.barcode = QLineEdit()
        self.unlink = QPushButton("Desvincular e cadastrar como novo")
        self.unlink.clicked.connect(self._unlink_selected)
        self.factor_kind = QComboBox(); self.factor_kind.addItem("Multiplicar", "MULTIPLICAR")
        self.factor_kind.addItem("Dividir", "DIVIDIR")
        self.factor = QLineEdit("1"); self.stock_unit = QComboBox()
        for code, description in self.application.units():
            self.stock_unit.addItem(f"{code} — {description}", code)
        self.conversion = QLabel(); self.save_item = QPushButton("Salvar edição deste item")
        self.save_item.setObjectName("primary"); self.save_item.clicked.connect(self._save_selected)
        for label, widget in (("Situação automática", self.status),
                              ("Nome do produto", self.name), ("Vínculo", self.linked_product),
                              ("", self.unlink),
                              ("Código de barras", self.barcode), ("Tipo de fator", self.factor_kind),
                              ("Fator informado", self.factor), ("Unidade de estoque/venda", self.stock_unit),
                              ("Resultado", self.conversion), ("", self.save_item)):
            form.addRow(label, widget)
        self.factor.textEdited.connect(self._preview_conversion)
        self.factor_kind.currentIndexChanged.connect(self._preview_conversion)
        splitter.addWidget(details); splitter.setSizes((1030, 380)); layout.addWidget(splitter, 1)
        nav = QHBoxLayout(); cancel = QPushButton("Cancelar [Esc]"); self.to_prices = QPushButton("Avançar para preços")
        self.to_prices.setObjectName("primary"); cancel.clicked.connect(self.reject); self.to_prices.clicked.connect(self._show_prices)
        nav.addStretch(); nav.addWidget(cancel); nav.addWidget(self.to_prices); layout.addLayout(nav)
        self.pages.addWidget(page)

    def _build_price_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        line = QHBoxLayout(); line.addWidget(QLabel("Margem para todos (%)")); self.bulk_margin = QLineEdit("0")
        apply_all = QPushButton("Aplicar a todos"); apply_all.clicked.connect(self._apply_bulk_margin)
        line.addWidget(self.bulk_margin); line.addWidget(apply_all); line.addStretch(); layout.addLayout(line)
        self.price_table = QTableWidget(0, 6)
        self.price_table.setHorizontalHeaderLabels((
            "Item", "Produto", "Custo unitário", "Margem %", "Preço de venda", "Alerta",
        ))
        self.price_table.setStyleSheet(WHITE_TABLE); self.price_table.setAlternatingRowColors(True)
        self.price_table.verticalHeader().setVisible(False); self.price_table.verticalHeader().setDefaultSectionSize(36)
        self.price_table.horizontalHeader().setSectionResizeMode(1, self.price_table.horizontalHeader().ResizeMode.Stretch)
        self.price_table.horizontalHeader().setSectionResizeMode(5, self.price_table.horizontalHeader().ResizeMode.Stretch)
        layout.addWidget(self.price_table, 1)
        self.final_summary = QLabel(); self.final_summary.setWordWrap(True); layout.addWidget(self.final_summary)
        nav = QHBoxLayout(); self.back_to_items = QPushButton("Voltar sem perder alterações"); self.review = QPushButton("Revisar entrada")
        self.review.setObjectName("primary"); self.back_to_items.clicked.connect(lambda: self.pages.setCurrentIndex(0)); self.review.clicked.connect(self._show_confirmation)
        nav.addWidget(self.back_to_items); nav.addStretch(); nav.addWidget(self.review); layout.addLayout(nav)
        self.pages.addWidget(page)

    def _build_confirmation_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel("REVISÃO FINAL — NENHUM DADO FOI GRAVADO AINDA"))
        self.confirmation_text = QTextEdit(); self.confirmation_text.setReadOnly(True)
        self.confirmation_text.setStyleSheet("background:#ffffff;color:#111827;border:1px solid #cbd5e1;padding:10px")
        layout.addWidget(self.confirmation_text, 1)
        nav = QHBoxLayout(); self.back_to_prices = QPushButton("Voltar aos preços")
        self.confirm = QPushButton("Confirmar entrada da nota")
        self.confirm.setObjectName("primary"); self.back_to_prices.clicked.connect(lambda: self.pages.setCurrentIndex(1)); self.confirm.clicked.connect(self._commit)
        nav.addWidget(self.back_to_prices); nav.addStretch(); nav.addWidget(self.confirm); layout.addLayout(nav)
        self.pages.addWidget(page)

    def _build_completion_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel("IMPORTAÇÃO CONCLUÍDA"))
        self.completion_text = QTextEdit(); self.completion_text.setReadOnly(True)
        self.completion_text.setStyleSheet("background:#ffffff;color:#111827;border:1px solid #cbd5e1;padding:10px")
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
                "candidates": candidates, "saved": saved, "saved_ok": True,
            })
            self._recalculate(index)

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
        for index, row in enumerate(self._rows):
            item = self.document.itens[index]
            mark = "● SALVO" if row["status"] == "SALVO" else "● EXATO" if row["status"] == "EXATO_NOVO" else "⚠ REVISAR" if row["produto_id"] else "NOVO"
            values = (mark, index + 1, item.codigo, row["descricao"], item.cfop,
                      _number(item.quantidade), item.unidade, row["fator"], row["unidade"],
                      _number(row["stock_quantity"]), _number(row["unit_cost"], 2))
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value)); cell.setToolTip(str(value))
                if column == 0:
                    cell.setForeground(QColor("#15803d" if row["status"] == "SALVO" else "#1d4ed8" if row["status"] == "EXATO_NOVO" else "#b45309"))
                self.table.setItem(index, column, cell)
        if self.table.rowCount() and self.table.currentRow() < 0: self.table.selectRow(0)
        self.table.blockSignals(False)
        if self.table.currentRow() >= 0:
            self._load_selected()

    def _load_selected(self):
        index = self.table.currentRow()
        if index < 0: return
        self._loading = True; row = self._rows[index]
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
        self.name.setText(row["descricao"]); self.barcode.setText(row["codigo_barras"])
        self.factor_kind.setCurrentIndex(max(0, self.factor_kind.findData(row["tipo_fator"])))
        self.factor.setText(str(row["fator"]).replace(".", ",")); self.stock_unit.setCurrentIndex(max(0, self.stock_unit.findData(row["unidade"])))
        self._loading = False; self._preview_conversion()

    def _selection_changed(self, current_row, _current_column, previous_row, _previous_column):
        if self._loading:
            return
        if previous_row >= 0 and previous_row != current_row and not self._save_selected(previous_row, show_error=False):
            self._loading = True; self.table.selectRow(previous_row); self._loading = False
            QMessageBox.warning(self, "Revisar item", "Corrija o item atual antes de selecionar outro.")
            return
        self._load_selected()

    def _unlink_selected(self):
        index = self.table.currentRow()
        if index < 0:
            return
        row = self._rows[index]
        row.update({"acao": "CRIAR", "produto_id": None, "saved": None, "status": "NOVO", "saved_ok": True})
        self._render_rows(); self.table.selectRow(index); self._load_selected()

    def _preview_conversion(self):
        if self._loading or self.table.currentRow() < 0: return
        try:
            entered = _decimal(self.factor.text(), "Fator", positive=True)
            factor = entered if self.factor_kind.currentData() == "MULTIPLICAR" else Decimal("1") / entered
            qty = Decimal(str(self.document.itens[self.table.currentRow()].quantidade)) * factor
            self.conversion.setText(f"{_number(qty)} {self.stock_unit.currentData() or 'UN'} entrarão no estoque")
        except ValueError:
            self.conversion.setText("Informe um fator positivo")

    def _save_selected(self, index=None, *, show_error=True):
        index = self.table.currentRow() if index is None else index
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
        self._recalculate(index); self._render_rows(); self.table.selectRow(index)
        return True

    def _show_prices(self):
        try:
            if not self._save_selected():
                return
            for index, row in enumerate(self._rows):
                if not row.get("saved_ok"): raise ValueError(f"Revise e salve o item {index + 1}.")
                self._recalculate(index)
        except ValueError as error:
            QMessageBox.warning(self, "Revisar produtos", str(error)); return
        self._render_prices(); self.pages.setCurrentIndex(1)

    def _render_prices(self):
        self.price_table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            fixed = (index + 1, row["descricao"], _number(row["unit_cost"], 2))
            for column, value in enumerate(fixed): self.price_table.setItem(index, column, QTableWidgetItem(str(value)))
            margin = QLineEdit(_number(row["margem"], 2)); price = QLineEdit(_number(row["preco"], 2))
            margin.textEdited.connect(lambda _text, i=index: self._margin_changed(i))
            price.textEdited.connect(lambda _text, i=index: self._price_changed(i))
            self.price_table.setCellWidget(index, 3, margin); self.price_table.setCellWidget(index, 4, price)
            self.price_table.setItem(index, 5, QTableWidgetItem(""))
        self._refresh_summary()

    def _margin_changed(self, index):
        if self._loading: return
        try:
            margin = _decimal(self.price_table.cellWidget(index, 3).text(), "Margem")
            self._rows[index]["margem"] = margin; self._recalculate(index)
            self._loading = True; self.price_table.cellWidget(index, 4).setText(_number(self._rows[index]["preco"], 2)); self._loading = False
            self.price_table.item(index, 5).setText("")
        except ValueError:
            self.price_table.item(index, 5).setText("Margem inválida")
        self._refresh_summary()

    def _price_changed(self, index):
        if self._loading: return
        try:
            price = _decimal(self.price_table.cellWidget(index, 4).text(), "Preço")
            cost = self._rows[index]["unit_cost"]
            margin = ((price / cost - 1) * 100).quantize(Decimal("0.01")) if cost else Decimal("0")
            if margin < 0: raise ValueError("Preço abaixo do custo")
            self._rows[index].update({"preco": price, "margem": margin})
            self._loading = True; self.price_table.cellWidget(index, 3).setText(_number(margin, 2)); self._loading = False
            self.price_table.item(index, 5).setText("")
        except (ValueError, InvalidOperation, ZeroDivisionError) as error:
            self.price_table.item(index, 5).setText(str(error))
        self._refresh_summary()

    def _apply_bulk_margin(self):
        try: margin = _decimal(self.bulk_margin.text(), "Margem geral")
        except ValueError as error: QMessageBox.warning(self, "Ajustar preços", str(error)); return
        for index, row in enumerate(self._rows):
            row["margem"] = margin; self._recalculate(index)
        self._render_prices()

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
        self.confirmation_text.setPlainText("\n".join(lines)); self.pages.setCurrentIndex(2)

    def _commit(self):
        if self._busy: return
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
        lines = [f"Importação nº {result.get('importacao_id', '—')} concluída.",
                 f"Produtos criados: {result.get('itens_criados', 0)}",
                 f"Produtos vinculados/atualizados: {result.get('itens_vinculados', 0)}",
                 f"Títulos financeiros: {len(result.get('titulo_ids') or ())}",
                 str(result.get('financeiro_indicacao') or "")]
        for item in result.get("resultados") or ():
            lines.append(f"• {item.get('descricao')} — {item.get('status')} — estoque +{item.get('quantidade_estoque')}")
        self.completion_text.setPlainText("\n".join(lines)); self.pages.setCurrentIndex(3)
