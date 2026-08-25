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
        cards = QGridLayout(); cards.setSpacing(12); self.cards = {}
        for index, (key, label, color, tint) in enumerate((
            ("sales", "VENDAS REALIZADAS HOJE", "#00e88a", "rgba(0,232,138,28)"),
            ("receipts", "RECEBIMENTOS DE FICHAS HOJE", "#58a6ff", "rgba(88,166,255,30)"),
            ("overdue", "COBRANÇAS VENCIDAS", "#f2cc60", "rgba(242,204,96,28)"),
            ("products", "PRODUTOS ATIVOS", "#a371f7", "rgba(163,113,247,30)"),
        )):
            card = QPushButton(f"{label}\n—"); card.setAccessibleName(label)
            card.setCursor(Qt.CursorShape.PointingHandCursor); card.setAutoRepeat(False)
            card.setToolTip(f"Abrir detalhes de {label.casefold()}")
            # Qt desconta a borda/padding efetivos do estilo em alguns backends.
            card.setStyleSheet(
                f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {tint},stop:1 #171d24);text-align:left;min-height:90px;"
                f"border:1px solid #30363d;border-bottom:5px solid {color};"
                f"border-radius:12px;padding:16px;color:{color};"
                "font-size:17px;font-weight:900}"
                f"QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {tint},stop:1 #202a35);border:2px solid {color};border-bottom:6px solid {color}}}"
                f"QPushButton:focus{{border:3px solid {color}}}"
            )
            # Aplicar depois do QSS: o min-height do tema não pode encolher o cartão.
            card.setFixedHeight(90)
            card.clicked.connect(lambda _checked=False, selected=key: self.open_detail(selected))
            cards.addWidget(card, index // 2, index % 2); self.cards[key] = (label, card)
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

    def open_detail(self, kind: str) -> bool:
        try:
            dialog = DashboardDetailDialog(self.application, kind, self)
            dialog.exec()
            self.cards[kind][1].setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        except Exception as error:
            QMessageBox.warning(self, "Detalhes do Início", str(error))
            return False

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


class DashboardDetailDialog(QDialog):
    TITLES = {
        "sales": "VENDAS REALIZADAS HOJE", "receipts": "RECEBIMENTOS DE FICHAS HOJE",
        "overdue": "COBRANÇAS VENCIDAS", "products": "PRODUTOS ATIVOS",
    }

    def __init__(self, application, kind: str, parent=None, *, page_size=50) -> None:
        super().__init__(parent); self.application = application; self.kind = kind
        self.page_size = max(10, min(int(page_size), 100)); self.offset = 0; self.total = 0
        if kind not in self.TITLES: raise ValueError("Cartão de detalhe inválido.")
        self.setWindowTitle(self.TITLES[kind]); self.resize(1080, 680); self.setMinimumSize(820, 520)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint |
                            Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(STYLE); root = QVBoxLayout(self)
        title = QLabel(self.TITLES[kind]); title.setStyleSheet("font-size:23px;font-weight:900;color:#58a6ff")
        root.addWidget(title)
        self.summary = QLabel(); root.addWidget(self.summary)
        self.table = QTableWidget(0, 6); self.table.setHorizontalHeaderLabels(
            ("ID", "Data / atualização", "Cliente / produto", "Descrição / código", "Valor", "Situação")
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)
        footer = QHBoxLayout(); self.page = QLabel(); self.previous = QPushButton("← Anterior")
        self.next = QPushButton("Próxima →"); close = QPushButton("Fechar [Esc]")
        self.previous.clicked.connect(self.previous_page); self.next.clicked.connect(self.next_page); close.clicked.connect(self.reject)
        footer.addWidget(self.page); footer.addStretch(); footer.addWidget(self.previous); footer.addWidget(self.next); footer.addWidget(close)
        root.addLayout(footer); QShortcut(QKeySequence("Esc"), self, activated=self.reject).setAutoRepeat(False)
        self.reload()

    def reload(self):
        detail = self.application.detail(self.kind, limit=self.page_size, offset=self.offset)
        self.total = detail.total_records; self.table.setRowCount(0)
        for item in detail.rows:
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (item.record_id, item.occurred_at, item.subject, item.description, _money(item.value), item.status)
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(str(value)))
        pages = max(1, (self.total + self.page_size - 1) // self.page_size)
        current = self.offset // self.page_size + 1
        self.summary.setText(f"{self.total} registro(s) • total { _money(detail.total_value) }")
        self.page.setText(f"Página {current} de {pages}")
        self.previous.setEnabled(self.offset > 0); self.next.setEnabled(self.offset + self.page_size < self.total)
        if self.table.rowCount(): self.table.selectRow(0)

    def previous_page(self):
        if self.offset <= 0: return
        self.offset = max(0, self.offset - self.page_size); self.reload()

    def next_page(self):
        if self.offset + self.page_size >= self.total: return
        self.offset += self.page_size; self.reload()
