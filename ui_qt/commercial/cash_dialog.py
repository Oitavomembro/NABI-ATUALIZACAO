from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from .widgets.money_edit import MoneyEdit


STYLE = """
QDialog { background:#0d1117;color:#f0f6fc; } QLabel { color:#f0f6fc; }
QLineEdit,QTableWidget { background:#161b22;color:#f0f6fc;border:1px solid #30363d;
 border-radius:6px;selection-background-color:#1f6feb; }
QLineEdit { min-height:38px;padding:0 9px; }
QPushButton { background:#30363d;color:#f0f6fc;border:0;border-radius:6px;
 min-height:40px;padding:0 14px;font-weight:700; }
QPushButton#primary { background:#1f6feb; } QPushButton#success { background:#2ea043; }
QHeaderView::section { background:#21262d;color:#f0f6fc;padding:9px;border:0;
 border-right:1px solid #30363d;font-weight:700; }
"""


def money(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class CashValueDialog(QDialog):
    def __init__(self, title: str, action_label: str, action, parent=None, *, note_required=False):
        super().__init__(parent)
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


class CashDialog(QDialog):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
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
            ("expected", "DINHEIRO ESPERADO"), ("cash", "VENDAS DINHEIRO"),
            ("pix", "PIX"), ("card", "CARTÃO"), ("supplies", "SUPRIMENTOS"),
            ("withdrawals", "SANGRIAS"),
        )
        for index, (key, text) in enumerate(labels):
            label = QLabel(); label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;font-weight:700")
            self.cards[key] = (text, label); cards.addWidget(label, index // 3, index % 3)
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
