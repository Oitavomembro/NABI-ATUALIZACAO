from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)
from .login_dialog import ADMIN_METALLIC_STYLE

STYLE = ADMIN_METALLIC_STYLE + "QDialog { font-size:14px; }"


class AuditDialog(QDialog):
    def __init__(self, application, parent=None):
        super().__init__(parent)
        self.application = application; self.entries = ()
        self.setWindowTitle("Auditoria administrativa")
        self.resize(1020, 620); self.setMinimumSize(760, 480); self.setStyleSheet(STYLE)
        root=QVBoxLayout(self); title=QLabel("HISTÓRICO DE LOGIN E SEGURANÇA")
        title.setStyleSheet("font-size:22px;font-weight:900;color:#e4e8eb;border-bottom:1px solid #73c7dc"); root.addWidget(title)
        row=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Filtrar por data, usuário, ação, resultado ou detalhe")
        self.refresh_button=QPushButton("Atualizar [F5]"); row.addWidget(self.search,1); row.addWidget(self.refresh_button); root.addLayout(row)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(("Data","Usuário","Ação","Resultado","Detalhes")); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.installEventFilter(self); root.addWidget(self.table,1)
        self.status=QLabel(); self.status.setStyleSheet("color:#aeb5bb"); root.addWidget(self.status)
        close=QPushButton("Fechar [Esc]"); close.clicked.connect(self.reject); root.addWidget(close,0,Qt.AlignmentFlag.AlignRight)
        self.search.textChanged.connect(self._render); self.refresh_button.clicked.connect(self.reload)
        self._escape=QShortcut(QKeySequence("Esc"),self); self._escape.setAutoRepeat(False); self._escape.activated.connect(self.reject)
        self._refresh=QShortcut(QKeySequence("F5"),self); self._refresh.setAutoRepeat(False); self._refresh.activated.connect(self.reload)
        self.reload(); self.search.setFocus(Qt.FocusReason.OtherFocusReason)

    def reload(self) -> None:
        page=self.application.load(limit=500); self.entries=page.entries; self._render()

    def _render(self, *_args) -> None:
        term=self.search.text().strip().casefold(); rows=[]
        for entry in self.entries:
            values=(entry.date,entry.user,entry.action,entry.result,entry.details)
            if not term or term in " ".join(values).casefold(): rows.append(values)
        self.table.setRowCount(len(rows))
        for row,values in enumerate(rows):
            for column,value in enumerate(values): self.table.setItem(row,column,QTableWidgetItem(value))
        for column in range(4): self.table.resizeColumnToContents(column)
        self.status.setText(f"{len(rows)} evento(s) exibido(s) • limite da consulta: 500")

    def eventFilter(self, watched, event) -> bool:
        if watched is self.table and event.type()==QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            event.accept(); return True
        return super().eventFilter(watched,event)
