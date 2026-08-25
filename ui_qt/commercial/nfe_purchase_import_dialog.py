from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
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
            "O XML é evidência local. Nenhum vínculo sugerido por nome e nenhum fator inferido "
            "serão confirmados automaticamente. A entrada ocorrerá somente no último botão."
        )
        warning.setWordWrap(True); warning.setStyleSheet("background:#2b2111;border-left:5px solid #d29922;padding:8px")
        root.addWidget(warning)
        self.pages = QStackedWidget(); root.addWidget(self.pages, 1)
        self._build_review_page(); self._build_price_page(); self._initialize_rows(); self._render_rows()
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
        self.table.itemSelectionChanged.connect(self._load_selected)
        splitter.addWidget(self.table)
        details = QWidget(); form = QFormLayout(details)
        self.status = QLabel(); self.action = QComboBox(); self.action.addItem("Criar novo produto", "CRIAR")
        self.action.addItem("Vincular sem alterar cadastro", "VINCULAR")
        self.action.addItem("Atualizar cadastro e vincular", "ATUALIZAR")
        self.product = QComboBox(); self.name = QLineEdit(); self.barcode = QLineEdit()
        self.factor_kind = QComboBox(); self.factor_kind.addItem("Multiplicar", "MULTIPLICAR")
        self.factor_kind.addItem("Dividir", "DIVIDIR")
        self.factor = QLineEdit("1"); self.stock_unit = QComboBox()
        for code, description in self.application.units():
            self.stock_unit.addItem(f"{code} — {description}", code)
        self.conversion = QLabel(); self.save_item = QPushButton("Salvar edição deste item")
        self.save_item.setObjectName("primary"); self.save_item.clicked.connect(self._save_selected)
        for label, widget in (("Situação", self.status), ("Decisão", self.action),
                              ("Produto cadastrado", self.product), ("Descrição de venda", self.name),
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
        self.price_table = QTableWidget(0, 7)
        self.price_table.setHorizontalHeaderLabels((
            "Item", "Produto", "Qtd. estoque", "Custo unitário", "Margem %", "Preço de venda", "Alerta",
        ))
        self.price_table.setStyleSheet(WHITE_TABLE); self.price_table.setAlternatingRowColors(True)
        self.price_table.verticalHeader().setVisible(False); self.price_table.verticalHeader().setDefaultSectionSize(36)
        self.price_table.horizontalHeader().setSectionResizeMode(1, self.price_table.horizontalHeader().ResizeMode.Stretch)
        self.price_table.horizontalHeader().setSectionResizeMode(6, self.price_table.horizontalHeader().ResizeMode.Stretch)
        layout.addWidget(self.price_table, 1)
        self.final_summary = QLabel(); self.final_summary.setWordWrap(True); layout.addWidget(self.final_summary)
        nav = QHBoxLayout(); back = QPushButton("Voltar sem perder alterações"); self.confirm = QPushButton("Revisar e confirmar entrada")
        self.confirm.setObjectName("primary"); back.clicked.connect(lambda: self.pages.setCurrentIndex(0)); self.confirm.clicked.connect(self._commit)
        nav.addWidget(back); nav.addStretch(); nav.addWidget(self.confirm); layout.addLayout(nav)
        self.pages.addWidget(page)

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

    def _load_selected(self):
        index = self.table.currentRow()
        if index < 0: return
        self._loading = True; row = self._rows[index]
        labels = {"SALVO": "Vínculo anterior confirmado", "EXATO_NOVO": "Coincidência exata nova — revisar", "REVISAR": "Sem vínculo exato — escolha humana", "NOVO": "Produto novo"}
        self.status.setText(labels.get(row["status"], row["status"]))
        self.action.setCurrentIndex(max(0, self.action.findData(row["acao"])))
        self.product.clear(); self.product.addItem("Nenhum — criar novo", None)
        known = set()
        if row["saved"]:
            self.product.addItem(f"ID {row['saved']['produto_id']} — {row['saved']['nome']}", int(row["saved"]["produto_id"])); known.add(int(row["saved"]["produto_id"]))
        for candidate in row["candidates"]:
            if candidate.product_id not in known:
                self.product.addItem(f"ID {candidate.product_id} — {candidate.description} ({candidate.criterion} {candidate.similarity}%)", candidate.product_id); known.add(candidate.product_id)
        self.product.setCurrentIndex(max(0, self.product.findData(row["produto_id"])))
        self.name.setText(row["descricao"]); self.barcode.setText(row["codigo_barras"])
        self.factor_kind.setCurrentIndex(max(0, self.factor_kind.findData(row["tipo_fator"])))
        self.factor.setText(str(row["fator"]).replace(".", ",")); self.stock_unit.setCurrentIndex(max(0, self.stock_unit.findData(row["unidade"])))
        self._loading = False; self._preview_conversion()

    def _preview_conversion(self):
        if self._loading or self.table.currentRow() < 0: return
        try:
            entered = _decimal(self.factor.text(), "Fator", positive=True)
            factor = entered if self.factor_kind.currentData() == "MULTIPLICAR" else Decimal("1") / entered
            qty = Decimal(str(self.document.itens[self.table.currentRow()].quantidade)) * factor
            self.conversion.setText(f"{_number(qty)} {self.stock_unit.currentData() or 'UN'} entrarão no estoque")
        except ValueError:
            self.conversion.setText("Informe um fator positivo")

    def _save_selected(self):
        index = self.table.currentRow()
        if index < 0: return False
        try:
            factor = _decimal(self.factor.text(), "Fator", positive=True)
            action = self.action.currentData(); product_id = self.product.currentData()
            if action in {"VINCULAR", "ATUALIZAR"} and not product_id:
                raise ValueError("Escolha um produto cadastrado para vincular ou atualizar.")
            if action == "CRIAR": product_id = None
            if not self.name.text().strip(): raise ValueError("A descrição de venda é obrigatória.")
        except ValueError as error:
            QMessageBox.warning(self, "Revisar item", str(error)); return False
        row = self._rows[index]; row.update({
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
            fixed = (index + 1, row["descricao"], _number(row["stock_quantity"]), _number(row["unit_cost"], 2))
            for column, value in enumerate(fixed): self.price_table.setItem(index, column, QTableWidgetItem(str(value)))
            margin = QLineEdit(_number(row["margem"], 2)); price = QLineEdit(_number(row["preco"], 2))
            margin.textEdited.connect(lambda _text, i=index: self._margin_changed(i))
            price.textEdited.connect(lambda _text, i=index: self._price_changed(i))
            self.price_table.setCellWidget(index, 4, margin); self.price_table.setCellWidget(index, 5, price)
            self.price_table.setItem(index, 6, QTableWidgetItem(""))
        self._refresh_summary()

    def _margin_changed(self, index):
        if self._loading: return
        try:
            margin = _decimal(self.price_table.cellWidget(index, 4).text(), "Margem")
            self._rows[index]["margem"] = margin; self._recalculate(index)
            self._loading = True; self.price_table.cellWidget(index, 5).setText(_number(self._rows[index]["preco"], 2)); self._loading = False
            self.price_table.item(index, 6).setText("")
        except ValueError:
            self.price_table.item(index, 6).setText("Margem inválida")
        self._refresh_summary()

    def _price_changed(self, index):
        if self._loading: return
        try:
            price = _decimal(self.price_table.cellWidget(index, 5).text(), "Preço")
            cost = self._rows[index]["unit_cost"]
            margin = ((price / cost - 1) * 100).quantize(Decimal("0.01")) if cost else Decimal("0")
            if margin < 0: raise ValueError("Preço abaixo do custo")
            self._rows[index].update({"preco": price, "margem": margin})
            self._loading = True; self.price_table.cellWidget(index, 4).setText(_number(margin, 2)); self._loading = False
            self.price_table.item(index, 6).setText("")
        except (ValueError, InvalidOperation, ZeroDivisionError) as error:
            self.price_table.item(index, 6).setText(str(error))
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

    def _commit(self):
        if self._busy: return
        for index in range(len(self._rows)):
            self._margin_changed(index)
        if any(self.price_table.item(i, 6).text() for i in range(len(self._rows))):
            QMessageBox.warning(self, "Revisar preços", "Corrija os preços destacados antes de confirmar."); return
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
        QMessageBox.information(self, "Importação concluída", "Produtos, vínculos e estoque foram gravados pela transação oficial.")
        self.accept()
