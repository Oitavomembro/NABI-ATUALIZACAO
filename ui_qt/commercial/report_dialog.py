from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QFileDialog, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from commercial.application.report_dto import ReportQuery


STYLE = """
QDialog { background:#111418; color:#edf0f2; font-size:14px; }
QLabel { color:#e8ebee; }
QLineEdit,QComboBox,QDateEdit,QTableWidget {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #292e33,stop:1 #171a1e);
 color:#f4f6f7; border:1px solid #555d65; border-radius:7px; min-height:38px;
 selection-background-color:#386b7b; selection-color:#fff; }
QLineEdit:focus,QComboBox:focus,QDateEdit:focus,QTableWidget:focus { border:1px solid #73c7dc; }
QPushButton {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #626a72,stop:.45 #41474d,stop:1 #272c31);
 color:#f6f7f8; border:1px solid #7a838b; border-radius:7px;
 min-height:40px; padding:0 14px; font-weight:700; }
QPushButton:hover { border-color:#a8b0b7; background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #737c84,stop:1 #343a40); }
QPushButton:focus { border:2px solid #73c7dc; }
QPushButton:disabled { color:#7f878e; background:#25292d; border-color:#3c4248; }
QPushButton#primary { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #567984,stop:1 #294852); border-color:#73c7dc; }
QHeaderView::section {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #555d65,stop:1 #292e33);
 color:#fff; padding:9px; border:0; border-right:1px solid #687078;
 border-bottom:1px solid #73c7dc; font-weight:800; }
QTableWidget { gridline-color:#3e454c; alternate-background-color:#20252a; }
"""


def _money(value) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class ReportDialog(QDialog):
    """Consulta e exportação; não executa operação fiscal nem altera registros operacionais."""

    def __init__(self, application, actor: str, parent=None) -> None:
        super().__init__(parent)
        self.application = application
        self.actor = str(actor or "").strip()
        self.current_document = None
        self.setWindowTitle("Relatórios")
        self.resize(1180, 760); self.setMinimumSize(900, 600); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("RELATÓRIOS E INDICADORES")
        title.setStyleSheet("font-size:24px;font-weight:900;color:#e4e8eb;border-bottom:1px solid #73c7dc")
        root.addWidget(title)

        filters = QGridLayout()
        self.report_type = QComboBox()
        for option in application.available_reports():
            self.report_type.addItem(option.title, option.report_id)
        today = QDate.currentDate()
        self.start_date = QDateEdit(QDate(today.year(), today.month(), 1))
        self.end_date = QDateEdit(today)
        for field in (self.start_date, self.end_date):
            field.setDisplayFormat("dd/MM/yyyy"); field.setCalendarPopup(True)
        self.search = QLineEdit(); self.search.setPlaceholderText("Pesquisar")
        self.status = QLineEdit(); self.status.setPlaceholderText("Status")
        self.user = QLineEdit(); self.user.setPlaceholderText("Usuário")
        self.generate_button = QPushButton("Calcular e listar  [Enter]")
        self.generate_button.setObjectName("primary")
        for column, (label, widget) in enumerate((
            ("Relatório", self.report_type), ("Data inicial", self.start_date),
            ("Data final", self.end_date), ("Pesquisa", self.search),
            ("Status", self.status), ("Usuário", self.user),
        )):
            filters.addWidget(QLabel(label), 0, column); filters.addWidget(widget, 1, column)
        filters.addWidget(self.generate_button, 1, 6)
        root.addLayout(filters)

        cards = QHBoxLayout()
        self.quantity = QLabel("REGISTROS\n0")
        self.total = QLabel("VALOR TOTAL\nR$ 0,00")
        self.indicators = QLabel("Vendas R$ 0,00  •  A receber R$ 0,00  •  Estoque baixo 0")
        for card in (self.quantity, self.total, self.indicators):
            card.setStyleSheet(
                "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #454b51,stop:1 #20252a);"
                "border:1px solid #687078;border-left:3px solid #73c7dc;border-radius:8px;"
                "padding:12px;font-size:16px;font-weight:800"
            )
            cards.addWidget(card, 1)
        root.addLayout(cards)

        self.table = QTableWidget(0, 0)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.csv = QPushButton("Exportar CSV")
        self.xlsx = QPushButton("Exportar Excel")
        self.pdf = QPushButton("Gerar PDF")
        close = QPushButton("Fechar  [Esc]"); close.clicked.connect(self.reject)
        for button, fmt in ((self.csv, "CSV"), (self.xlsx, "XLSX"), (self.pdf, "PDF")):
            button.setEnabled(False); button.clicked.connect(lambda _checked=False, f=fmt: self.export(f))
            buttons.addWidget(button)
        buttons.addStretch(); buttons.addWidget(close); root.addLayout(buttons)

        self._fields = (
            self.report_type, self.start_date, self.end_date, self.search,
            self.status, self.user, self.generate_button,
        )
        for field in self._fields: field.installEventFilter(self)
        self.generate_button.clicked.connect(self.generate)
        shortcut = QShortcut(QKeySequence("F5"), self)
        shortcut.setAutoRepeat(False); shortcut.activated.connect(self.generate)
        escape = QShortcut(QKeySequence("Esc"), self)
        escape.setAutoRepeat(False); escape.activated.connect(self.reject)
        self.report_type.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {
            Qt.Key.Key_Return, Qt.Key.Key_Enter,
        }:
            if event.isAutoRepeat():
                event.accept(); return True
            index = self._fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._fields[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.generate_button:
                self.generate()
            else:
                self._fields[min(index + 1, len(self._fields) - 1)].setFocus(
                    Qt.FocusReason.TabFocusReason
                )
            event.accept(); return True
        return super().eventFilter(watched, event)

    def _query(self) -> ReportQuery:
        return ReportQuery(
            report_id=str(self.report_type.currentData() or ""),
            start_date=self.start_date.date().toString("dd/MM/yyyy"),
            end_date=self.end_date.date().toString("dd/MM/yyyy"),
            search=self.search.text(), status=self.status.text(), user=self.user.text(),
        )

    def generate(self) -> None:
        try:
            document = self.application.generate(self._query(), actor=self.actor)
            summary = self.application.summary(document)
            indicators = self.application.indicators(
                self.start_date.date().toString("dd/MM/yyyy"),
                self.end_date.date().toString("dd/MM/yyyy"),
            )
        except Exception as error:
            QMessageBox.warning(self, "Relatórios", str(error)); self.search.setFocus(); return
        self.current_document = document
        self.table.clear(); self.table.setColumnCount(len(document.columns))
        self.table.setHorizontalHeaderLabels(
            [column.replace("_", " ").title() for column in document.columns]
        )
        self.table.setRowCount(len(document.rows))
        for row, values in enumerate(document.rows):
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem("" if value is None else str(value)))
        self.quantity.setText(f"REGISTROS\n{summary.quantity}")
        self.total.setText(f"VALOR TOTAL\n{_money(summary.value_total)}")
        self.indicators.setText(
            f"Vendas {_money(indicators.sales_total)}  •  "
            f"A receber {_money(indicators.receivable_open)}  •  "
            f"Estoque baixo {indicators.low_stock}"
        )
        for button in (self.csv, self.xlsx, self.pdf): button.setEnabled(True)
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def export(self, fmt: str) -> None:
        if self.current_document is None:
            return
        extension = {"CSV": ".csv", "XLSX": ".xlsx", "PDF": ".pdf"}[fmt]
        destination, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório", f"{self.current_document.report_id}{extension}",
            f"Arquivo {fmt} (*{extension})",
        )
        if not destination: return
        try:
            path = self.application.export(
                self.current_document, fmt, Path(destination), actor=self.actor
            )
        except Exception as error:
            QMessageBox.critical(self, "Exportação", str(error)); return
        QMessageBox.information(self, "Relatório exportado", f"Arquivo salvo em:\n{path}")
