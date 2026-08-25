from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from commercial.application.cash_application_service import CashDetailSnapshot
from .widgets.money_edit import MoneyEdit


STYLE = """
QDialog { background:#0d1117;color:#f0f6fc; } QLabel { color:#f0f6fc; }
QLineEdit,QTableWidget { background:#161b22;color:#f0f6fc;border:1px solid #30363d;
 border-radius:6px;selection-background-color:#1f6feb; }
QLineEdit { min-height:38px;padding:0 9px; }
QPushButton { background:#30363d;color:#f0f6fc;border:0;border-radius:6px;
 min-height:40px;padding:0 14px;font-weight:700; }
QPushButton#primary { background:#1f6feb; } QPushButton#success { background:#2ea043; }
QPushButton#cashSummaryCard { background:#161b22;border:1px solid #30363d;
 border-radius:8px;padding:12px;font-weight:700;text-align:center;min-height:72px; }
QPushButton#cashSummaryCard:focus { border:2px solid #58a6ff;background:#1f2937; }
QHeaderView::section { background:#21262d;color:#f0f6fc;padding:9px;border:0;
 border-right:1px solid #30363d;font-weight:700; }
"""


def money(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _main_window_controls(dialog: QDialog) -> None:
    dialog.setModal(False)
    dialog.setWindowFlags(
        dialog.windowFlags()
        | Qt.WindowType.WindowMinimizeButtonHint
        | Qt.WindowType.WindowMaximizeButtonHint
        | Qt.WindowType.WindowCloseButtonHint
    )


def _modal_window_controls(dialog: QDialog) -> None:
    dialog.setModal(True)
    dialog.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False)
    dialog.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
    dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)


class CashValueDialog(QDialog):
    def __init__(self, title: str, action_label: str, action, parent=None, *, note_required=False):
        super().__init__(parent)
        _modal_window_controls(self)
        self.action = action
        self.note_required = note_required
        self.completed = False
        self.setWindowTitle(title); self.setMinimumWidth(480); self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        heading = QLabel(title.upper()); heading.setStyleSheet("font-size:20px;font-weight:800;color:#00d084")
        layout.addWidget(heading)
        self.amount = MoneyEdit(); self.amount.setAccessibleName("Valor")
        self.note = QLineEdit(); self.note.setPlaceholderText("Observação / motivo")
        self.confirm = QPushButton(action_label); self.confirm.setObjectName("success")
        cancel = QPushButton("Cancelar  [Esc]")
        layout.addWidget(QLabel("Valor")); layout.addWidget(self.amount)
        layout.addWidget(QLabel("Observação")); layout.addWidget(self.note)
        row = QHBoxLayout(); row.addStretch(); row.addWidget(cancel); row.addWidget(self.confirm)
        layout.addLayout(row)
        cancel.clicked.connect(self.reject); self.confirm.clicked.connect(self._execute)
        self._fields = (self.amount, self.note, self.confirm)
        for field in self._fields: field.installEventFilter(self)
        self.amount.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.isAutoRepeat(): event.accept(); return True
            index = self._fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._fields[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.confirm:
                self._execute()
            else:
                self._fields[index + 1].setFocus(Qt.FocusReason.TabFocusReason)
            event.accept(); return True
        return super().eventFilter(watched, event)

    def _execute(self):
        if self.note_required and not self.note.text().strip():
            QMessageBox.warning(self, "Caixa", "Informe a observação da diferença.")
            self.note.setFocus(); return
        try:
            self.action(self.amount.value(), self.note.text().strip())
        except Exception as exc:
            QMessageBox.warning(self, "Caixa", str(exc)); return
        self.completed = True; self.accept()


class CashDetailDialog(QDialog):
    """Paginação somente leitura de uma fotografia reconciliável do Caixa."""

    def __init__(self, snapshot: CashDetailSnapshot, parent=None, *, page_size=50):
        super().__init__(parent)
        if not isinstance(snapshot, CashDetailSnapshot):
            raise TypeError("O detalhamento do Caixa deve usar uma fotografia tipada.")
        _modal_window_controls(self)
        self.snapshot = snapshot
        self.page_size = int(page_size)
        self.current_page = 1
        self.setWindowTitle(f"Caixa — {snapshot.label.title()}")
        self.resize(1160, 700)
        self.setMinimumSize(900, 560)
        self.setStyleSheet(STYLE)

        layout = QVBoxLayout(self)
        heading = QLabel(snapshot.label)
        heading.setStyleSheet("font-size:22px;font-weight:900;color:#00d084")
        layout.addWidget(heading)
        if snapshot.session_id is None:
            period_text = "Nenhuma sessão de caixa aberta."
        else:
            period_text = (
                f"Sessão #{snapshot.session_id}  •  Período: {snapshot.period_start} até "
                f"{snapshot.period_end or 'EM ANDAMENTO'}"
            )
        self.period = QLabel(period_text)
        self.period.setAccessibleName("Período comprovado do detalhamento")
        layout.addWidget(self.period)
        self.reconciliation = QLabel()
        self.reconciliation.setAccessibleName("Reconciliação do detalhamento")
        layout.addWidget(self.reconciliation)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Data", "Origem", "Tipo", "Valor", "Responsável", "Documento",
            "Observação",
        ])
        self.table.setAccessibleName(f"Detalhamento de {snapshot.label.lower()}")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        controls = QHBoxLayout()
        self.previous_button = QPushButton("Página anterior  [PgUp]")
        self.next_button = QPushButton("Próxima página  [PgDown]")
        self.page_label = QLabel()
        close_button = QPushButton("Fechar  [Esc]")
        self.previous_button.clicked.connect(lambda: self.show_page(self.current_page - 1))
        self.next_button.clicked.connect(lambda: self.show_page(self.current_page + 1))
        close_button.clicked.connect(self.accept)
        controls.addWidget(self.previous_button)
        controls.addWidget(self.page_label)
        controls.addWidget(self.next_button)
        controls.addStretch()
        controls.addWidget(close_button)
        layout.addLayout(controls)
        self._shortcuts = []
        for key, callback in (
            ("PgUp", lambda: self.show_page(self.current_page - 1)),
            ("PgDown", lambda: self.show_page(self.current_page + 1)),
            ("Esc", self.reject),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        self.show_page(1)

    def show_page(self, number: int) -> bool:
        try:
            page = self.snapshot.page(number, page_size=self.page_size)
        except ValueError:
            return False
        self.current_page = page.page
        self.table.setRowCount(0)
        for item in page.items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (
                item.occurred_at, item.origin, item.movement_type, money(item.amount),
                item.responsible or "—", item.document or "—", item.note or "—",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.page_label.setText(
            f"Página {page.page} de {page.total_pages}  •  {page.total_items} lançamento(s)"
        )
        self.previous_button.setEnabled(page.page > 1)
        self.next_button.setEnabled(page.page < page.total_pages)
        status = "RECONCILIADO" if page.reconciled else "NÃO RECONCILIADO"
        color = "#5df2a1" if page.reconciled else "#ff8582"
        self.reconciliation.setText(
            f"CARD: {money(page.card_total)}  •  SOMA DO DETALHE: "
            f"{money(page.detail_total)}  •  {status}"
        )
        self.reconciliation.setStyleSheet(f"font-size:15px;font-weight:900;color:{color}")
        return True


class CashDialog(QDialog):
    def __init__(self, service, parent=None, *, detail_dialog_factory=CashDetailDialog):
        super().__init__(parent)
        _main_window_controls(self)
        self.service = service
        self.detail_dialog_factory = detail_dialog_factory
        self._detail_open = False
        self.setWindowTitle("Caixa"); self.resize(1050, 700); self.setMinimumSize(820, 560)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("CAIXA"); title.setStyleSheet("font-size:24px;font-weight:800;color:#00d084")
        self.status = QLabel(); self.status.setStyleSheet("font-size:16px;font-weight:800")
        header.addWidget(title); header.addStretch(); header.addWidget(self.status)
        layout.addLayout(header)
        cards = QGridLayout(); self.cards = {}
        labels = (
            ("expected", "DINHEIRO ESPERADO", "Detalhar dinheiro esperado"),
            ("cash", "VENDAS DINHEIRO", "Detalhar vendas em dinheiro"),
            ("pix", "PIX", "Detalhar vendas em PIX"),
            ("card", "CARTÃO", "Detalhar vendas em cartão"),
            ("supplies", "SUPRIMENTOS", "Detalhar suprimentos"),
            ("withdrawals", "SANGRIAS", "Detalhar sangrias"),
        )
        self._card_by_button = {}
        for index, (key, text, accessible_name) in enumerate(labels):
            button = QPushButton()
            button.setObjectName("cashSummaryCard")
            button.setAccessibleName(accessible_name)
            button.installEventFilter(self)
            button.clicked.connect(
                lambda _checked=False, selected=key: self.open_detail(selected)
            )
            self.cards[key] = (text, button)
            self._card_by_button[button] = key
            cards.addWidget(button, index // 3, index % 3)
        layout.addLayout(cards)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Data", "Tipo", "Valor", "Responsável", "Observação"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False); layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.open_button = QPushButton("Abrir caixa")
        self.open_zero_button = QPushButton("Abrir sem informar")
        self.supply_button = QPushButton("Suprimento")
        self.withdraw_button = QPushButton("Sangria")
        self.close_button = QPushButton("Fechar caixa")
        close_window = QPushButton("Fechar janela  [Esc]")
        self.open_button.setObjectName("success"); self.close_button.setObjectName("primary")
        self.open_button.clicked.connect(self.open_cash)
        self.open_zero_button.clicked.connect(self.open_without_value)
        self.supply_button.clicked.connect(lambda: self.movement("SUPRIMENTO"))
        self.withdraw_button.clicked.connect(lambda: self.movement("SANGRIA"))
        self.close_button.clicked.connect(self.close_cash); close_window.clicked.connect(self.reject)
        for button in (self.open_button, self.open_zero_button, self.supply_button, self.withdraw_button, self.close_button):
            row.addWidget(button)
        row.addStretch(); row.addWidget(close_window); layout.addLayout(row)
        QShortcut(QKeySequence("Esc"), self, activated=self.reject).setAutoRepeat(False)
        self.reload()

    def eventFilter(self, watched, event) -> bool:
        if (
            watched in self._card_by_button
            and event.type() == QEvent.Type.KeyPress
            and event.key() in {
                Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Left,
                Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
            }
        ):
            event.accept()
            if event.isAutoRepeat():
                return True
            buttons = tuple(self._card_by_button)
            index = buttons.index(watched)
            key = event.key()
            if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                self.open_detail(self._card_by_button[watched])
            else:
                delta = {
                    Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1,
                    Qt.Key.Key_Up: -3, Qt.Key.Key_Down: 3,
                    Qt.Key.Key_Return: -1, Qt.Key.Key_Enter: -1,
                }[key]
                target = max(0, min(len(buttons) - 1, index + delta))
                buttons[target].setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        return super().eventFilter(watched, event)

    def open_detail(self, key: str) -> bool:
        if self._detail_open:
            return False
        self._detail_open = True
        try:
            snapshot = self.service.detail_snapshot(key)
            dialog = self.detail_dialog_factory(snapshot, self)
            if not isinstance(dialog, QDialog):
                raise TypeError("O detalhamento deve abrir uma janela Qt.")
            dialog.exec()
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Caixa", str(exc))
            return False
        finally:
            self._detail_open = False

    def reload(self):
        try: state = self.service.current()
        except Exception as exc: QMessageBox.warning(self, "Caixa", str(exc)); return
        self.state = state
        self.status.setText("CAIXA ABERTO" if state.is_open else "CAIXA FECHADO")
        values = dict(expected=state.expected_cash, cash=state.cash_sales, pix=state.pix_sales,
                      card=state.card_sales, supplies=state.supplies, withdrawals=state.withdrawals)
        for key, value in values.items():
            text, label = self.cards[key]; label.setText(f"{text}\n{money(value)}")
        self.table.setRowCount(0)
        for movement in state.movements:
            row = self.table.rowCount(); self.table.insertRow(row)
            sign = "-" if movement.sign < 0 else "+"
            for column, value in enumerate((movement.occurred_at, movement.movement_type,
                                             f"{sign}{money(movement.amount)}", movement.user, movement.note)):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        for button in (self.supply_button, self.withdraw_button, self.close_button): button.setEnabled(state.is_open)
        self.open_button.setEnabled(not state.is_open); self.open_zero_button.setEnabled(not state.is_open)

    def open_cash(self):
        dialog = CashValueDialog("Abertura de caixa", "Confirmar abertura",
                                 lambda amount, _note: self.service.open(amount, informed=True), self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.reload()

    def open_without_value(self):
        try: self.service.open(Decimal("0"), informed=False)
        except Exception as exc: QMessageBox.warning(self, "Caixa", str(exc)); return
        self.reload()

    def movement(self, kind):
        dialog = CashValueDialog(kind.title(), f"Confirmar {kind.lower()}",
                                 lambda amount, note: self.service.register_movement(kind, amount, note), self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.reload()

    def close_cash(self):
        expected = self.state.expected_cash
        dialog = CashValueDialog("Fechamento de caixa", "Confirmar fechamento",
                                 lambda amount, note: self.service.close(amount, note), self)
        dialog.amount.set_value(expected)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.reload()
