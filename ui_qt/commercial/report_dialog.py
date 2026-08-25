from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, QEvent, QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QFileDialog, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from commercial.application.report_dto import ReportQuery


STYLE = """
QDialog { background:#0d1117; color:#f0f6fc; font-size:14px; }
QLabel { color:#f0f6fc; }
QLineEdit,QComboBox,QDateEdit,QTableWidget { background:#161b22; color:#f0f6fc;
 border:1px solid #30363d; border-radius:6px; min-height:38px; }
QPushButton { background:#30363d; color:#f0f6fc; border:0; border-radius:6px;
 min-height:40px; padding:0 14px; font-weight:700; }
QPushButton#primary { background:#238636; }
QHeaderView::section { background:#21262d; color:#f0f6fc; padding:9px;
 border:0; border-right:1px solid #30363d; font-weight:800; }
"""


def _money(value) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class _WorkerSignals(QObject):
    done = Signal(int, object)
    failed = Signal(int, str)


class _ReportLoad(QRunnable):
    def __init__(self,generation,application,query,actor,limit,offset):
        super().__init__(); self.generation=generation; self.application=application; self.query=query; self.actor=actor; self.limit=limit; self.offset=offset; self.signals=_WorkerSignals()
    def run(self):
        try:
            page=self.application.load_page(self.query,limit=self.limit,offset=self.offset,actor=self.actor)
            indicators=self.application.indicators(self.query.start_date,self.query.end_date)
            self.signals.done.emit(self.generation,(page,indicators))
        except Exception as error:self.signals.failed.emit(self.generation,str(error))


class _ReportExport(QRunnable):
    def __init__(self,generation,application,query,fmt,destination,actor):
        super().__init__(); self.generation=generation; self.application=application; self.query=query; self.fmt=fmt; self.destination=destination; self.actor=actor; self.signals=_WorkerSignals()
    def run(self):
        try:self.signals.done.emit(self.generation,self.application.export_query(self.query,self.fmt,self.destination,actor=self.actor))
        except Exception as error:self.signals.failed.emit(self.generation,str(error))


class ReportDialog(QDialog):
    """Consulta e exportação; não executa operação fiscal nem altera registros operacionais."""

    def __init__(self, application, actor: str, parent=None, *, page_size=100, thread_pool=None) -> None:
        super().__init__(parent)
        self.application = application
        self.actor = str(actor or "").strip()
        self.current_document = None
        self.current_query = None; self.page_size=min(max(int(page_size),25),500); self.offset=0; self._generation=0; self._pool=thread_pool or QThreadPool.globalInstance()
        self.setWindowTitle("Relatórios")
        self.resize(1180, 760); self.setMinimumSize(900, 600); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("RELATÓRIOS E INDICADORES")
        title.setStyleSheet("font-size:24px;font-weight:900;color:#58a6ff")
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
                "background:#161b22;border:1px solid #30363d;border-radius:8px;"
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

        navigation=QHBoxLayout(); self.previous=QPushButton("Página anterior [PgUp]"); self.page_label=QLabel("Página 1 de 1"); self.following=QPushButton("Próxima página [PgDown]"); self.load_state=QLabel("Pronto."); navigation.addWidget(self.previous); navigation.addWidget(self.page_label); navigation.addWidget(self.following); navigation.addStretch(); navigation.addWidget(self.load_state); root.addLayout(navigation)
        self.previous.clicked.connect(lambda:self.change_page(-1)); self.following.clicked.connect(lambda:self.change_page(1))

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
        for key,callback in (("PgUp",lambda:self.change_page(-1)),("PgDown",lambda:self.change_page(1))):
            shortcut=QShortcut(QKeySequence(key),self); shortcut.setAutoRepeat(False); shortcut.activated.connect(callback)
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
        self.offset=0; self.current_query=self._query(); self._start_load()

    def _start_load(self):
        if self.current_query is None:return
        self._generation+=1; generation=self._generation; self.load_state.setText("Carregando…"); self.generate_button.setEnabled(False)
        worker=_ReportLoad(generation,self.application,self.current_query,self.actor,self.page_size,self.offset); worker.signals.done.connect(self._loaded); worker.signals.failed.connect(self._failed); self._pool.start(worker)

    def _loaded(self,generation,payload):
        if generation!=self._generation:return
        page,indicators=payload; document=page.document; summary=page.summary; self.current_document=document
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
        current=(page.offset//page.limit)+1; pages=max(1,(page.total_records+page.limit-1)//page.limit); self.page_label.setText(f"Página {current} de {pages} — {page.total_records} registros"); self.previous.setEnabled(page.offset>0); self.following.setEnabled(page.offset+page.limit<page.total_records); self.load_state.setText("Sem resultados." if not document.rows else "Dados atualizados."); self.generate_button.setEnabled(True)
        self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _failed(self,generation,message):
        if generation!=self._generation:return
        self.load_state.setText(f"Erro: {message}"); self.generate_button.setEnabled(True); self.search.setFocus()

    def change_page(self,direction):
        if self.current_query is None:return
        self.offset=max(0,self.offset+(self.page_size if direction>0 else -self.page_size)); self._start_load()

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
            self._generation+=1; generation=self._generation; self.load_state.setText("Exportando período completo…")
            worker=_ReportExport(generation,self.application,self.current_query,fmt,Path(destination),self.actor); worker.signals.done.connect(self._exported); worker.signals.failed.connect(self._failed); self._pool.start(worker)
        except Exception as error: QMessageBox.critical(self,"Exportação",str(error))

    def _exported(self,generation,path):
        if generation!=self._generation:return
        self.load_state.setText("Exportação concluída."); QMessageBox.information(self,"Relatório exportado",f"Arquivo salvo em:\n{path}")

    def closeEvent(self,event):
        self._generation+=1; super().closeEvent(event)
