from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)


STYLE = """
QDialog{background:#161b22;color:#f0f6fc;font-size:14px} QLabel{color:#f0f6fc}
QPushButton{background:#30363d;color:#f0f6fc;border:0;border-radius:6px;min-height:40px;padding:0 14px;font-weight:800}
QPushButton:focus{border:2px solid #58a6ff} QTableWidget{background:#0d1117;color:#f0f6fc;border:1px solid #30363d;selection-background-color:#1f6feb}
QHeaderView::section{background:#21262d;color:#f0f6fc;padding:9px;border:0;border-right:1px solid #30363d;font-weight:800}
"""


def _money(value) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class _DashboardSignals(QObject):
    completed = Signal(int, object, object)


class DashboardLoadWorker(QRunnable):
    def __init__(self, generation: int, application, *, limit: int, offset: int) -> None:
        super().__init__(); self.generation = generation; self.application = application
        self.limit = limit; self.offset = offset; self.signals = _DashboardSignals()

    @Slot()
    def run(self) -> None:
        try: result, error = self.application.load(limit=self.limit, offset=self.offset), None
        except Exception as caught: result, error = None, caught
        self.signals.completed.emit(self.generation, result, error)


class DashboardDialog(QDialog):
    """Início somente leitura, paginado e carregado fora da thread da interface."""

    def __init__(
        self, application, parent=None, *, worker_pool=None, page_size: int = 50,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent); self.application = application
        self.embedded = bool(embedded)
        if self.embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        self.pool = worker_pool or QThreadPool.globalInstance()
        self.page_size = max(10, min(int(page_size), 100)); self.offset = 0
        self.total_records = 0; self._generation = 0; self._workers = []
        self.setWindowTitle("Início"); self.resize(1180, 740); self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLE); root = QVBoxLayout(self)
        heading = QHBoxLayout(); title = QLabel("INÍCIO")
        title.setStyleSheet("font-size:26px;font-weight:900;color:#00d084")
        self.loading = QLabel("Carregando..."); self.loading.setStyleSheet("color:#8b949e")
        heading.addWidget(title); heading.addStretch(); heading.addWidget(self.loading); root.addLayout(heading)
        cards = QGridLayout(); self.cards = {}
        for column, (key, label, color) in enumerate((
            ("sales", "VENDAS REALIZADAS HOJE", "#00ff88"),
            ("receipts", "RECEBIMENTOS DE FICHAS HOJE", "#58a6ff"),
            ("overdue", "COBRANÇAS VENCIDAS", "#f2cc60"),
            ("products", "PRODUTOS ATIVOS", "#a371f7"),
        )):
            card = QLabel(f"{label}\n—"); card.setAccessibleName(label)
            card.setStyleSheet(f"background:#0d1117;border-radius:9px;padding:14px;color:{color};font-size:16px;font-weight:900")
            cards.addWidget(card, 0, column); self.cards[key] = (label, card)
        root.addLayout(cards)
        subtitle = QLabel("HISTÓRICO DE MOVIMENTAÇÕES DO DIA")
        subtitle.setStyleSheet("font-size:17px;font-weight:900"); root.addWidget(subtitle)
        self.table = QTableWidget(0, 6); self.table.setHorizontalHeaderLabels(
            ("ID", "Horário", "Cliente", "Tipo", "Descrição / Produto", "Valor")
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(38)
        header = self.table.horizontalHeader(); header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch); self.table.installEventFilter(self)
        root.addWidget(self.table, 1)
        footer = QHBoxLayout(); self.page_label = QLabel("Página 1")
        self.previous = QPushButton("← Anterior  [PgUp]"); self.next = QPushButton("Próxima  [PgDn] →")
        self.refresh = QPushButton("Atualizar")
        self.previous.clicked.connect(self.previous_page); self.next.clicked.connect(self.next_page)
        self.refresh.clicked.connect(self.reload)
        footer.addWidget(self.page_label); footer.addStretch()
        for button in (self.previous, self.next, self.refresh): footer.addWidget(button)
        if not self.embedded:
            close = QPushButton("Fechar  [Esc]")
            close.clicked.connect(self.reject)
            footer.addWidget(close)
        root.addLayout(footer); self._shortcuts = []
        shortcuts = [("PgUp", self.previous_page), ("PgDown", self.next_page)]
        if not self.embedded:
            shortcuts.extend((("F5", self.reload), ("Esc", self.reject)))
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self); shortcut.setAutoRepeat(False)
            shortcut.activated.connect(callback); self._shortcuts.append(shortcut)
        self.reload()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.table and event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept(); return True
        return super().eventFilter(watched, event)

    def reload(self) -> None:
        self._generation += 1; generation = self._generation
        self.loading.setText("Carregando..."); self.refresh.setEnabled(False)
        worker = DashboardLoadWorker(generation, self.application, limit=self.page_size, offset=self.offset)
        worker.signals.completed.connect(self._loaded); self._workers.append(worker); self.pool.start(worker)

    def _loaded(self, generation: int, snapshot, error) -> None:
        self._workers = [worker for worker in self._workers if worker.generation != generation]
        if generation != self._generation: return
        self.refresh.setEnabled(True); self.loading.setText("")
        if error is not None:
            QMessageBox.warning(self, "Início", str(error)); return
        indicators, history = snapshot.indicators, snapshot.history
        self.cards["sales"][1].setText(f"{self.cards['sales'][0]}\n{_money(history.sales_total)}")
        self.cards["receipts"][1].setText(f"{self.cards['receipts'][0]}\n{_money(history.received_total)}")
        self.cards["overdue"][1].setText(f"{self.cards['overdue'][0]}\n{indicators.overdue_count} • {_money(indicators.overdue_value)}")
        products = "Indisponível" if indicators.active_products is None else str(indicators.active_products)
        self.cards["products"][1].setText(f"{self.cards['products'][0]}\n{products}")
        self.total_records = history.total_records; self.table.setRowCount(0)
        for movement in history.movements:
            row = self.table.rowCount(); self.table.insertRow(row)
            hour = movement.timestamp.split(" ", 1)[1] if " " in movement.timestamp else movement.timestamp
            values = (movement.movement_id, hour, movement.customer_name, movement.movement_type, movement.description, _money(movement.value))
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(str(value)))
        page = self.offset // self.page_size + 1; pages = max(1, (self.total_records + self.page_size - 1) // self.page_size)
        self.page_label.setText(f"Página {page} de {pages} • {self.total_records} registros")
        self.previous.setEnabled(self.offset > 0); self.next.setEnabled(self.offset + self.page_size < self.total_records)
        if self.table.rowCount(): self.table.selectRow(0)

    def previous_page(self) -> None:
        if self.offset <= 0: return
        self.offset = max(0, self.offset - self.page_size); self.reload()

    def next_page(self) -> None:
        if self.offset + self.page_size >= self.total_records: return
        self.offset += self.page_size; self.reload()
