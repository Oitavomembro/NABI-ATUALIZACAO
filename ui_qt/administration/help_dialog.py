from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.context_help import ContextHelpRegistry
from .login_dialog import ADMIN_METALLIC_STYLE

STYLE = ADMIN_METALLIC_STYLE + "QDialog { font-size:14px; }"


class HelpDialog(QDialog):
    """Apresentação Qt somente leitura do catálogo de ajuda do Legacy."""

    def __init__(self, registry=None, parent=None, *, context="global"):
        super().__init__(parent)
        self.registry = registry or ContextHelpRegistry()
        self.setWindowTitle("Central de Ajuda NabiCode")
        self.resize(820, 600); self.setMinimumSize(660, 460); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("CENTRAL DE AJUDA"); title.setStyleSheet("font-size:24px;font-weight:900;color:#e4e8eb;border-bottom:1px solid #73c7dc")
        root.addWidget(title)
        row = QHBoxLayout(); self.topic = QComboBox(); self.search = QLineEdit(); self.search.setPlaceholderText("Pesquisar tecla ou ação")
        row.addWidget(QLabel("Assunto")); row.addWidget(self.topic, 1); row.addWidget(self.search, 2); root.addLayout(row)
        self.description = QLabel(); self.description.setWordWrap(True); self.description.setStyleSheet("color:#d9dee2")
        root.addWidget(self.description)
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(("Tecla", "Ação")); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.installEventFilter(self); root.addWidget(self.table, 1)
        self.notes = QLabel(); self.notes.setWordWrap(True); self.notes.setStyleSheet("color:#aeb5bb"); root.addWidget(self.notes)
        close = QPushButton("Fechar [Esc]"); close.clicked.connect(self.reject); root.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self._contexts = self.registry.contexts()
        for key in self._contexts: self.topic.addItem(self.registry.get(key).title, key)
        target = self.registry.normalize_context(context); index = self.topic.findData(target); self.topic.setCurrentIndex(max(0, index))
        self.topic.currentIndexChanged.connect(self.refresh); self.search.textChanged.connect(self.refresh)
        self._escape = QShortcut(QKeySequence("Esc"), self); self._escape.setAutoRepeat(False); self._escape.activated.connect(self.reject)
        self.refresh(); self.search.setFocus(Qt.FocusReason.OtherFocusReason)

    def refresh(self, *_args) -> None:
        topic = self.registry.get(self.topic.currentData() or "global")
        term = self.search.text().strip().casefold(); rows = []
        for shortcut in topic.shortcuts:
            if not term or term in f"{shortcut.keys} {shortcut.action}".casefold(): rows.append(shortcut)
        self.description.setText(topic.description); self.notes.setText("\n".join(f"• {note}" for note in topic.notes))
        self.table.setRowCount(len(rows))
        for row, shortcut in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(shortcut.keys)); self.table.setItem(row, 1, QTableWidgetItem(shortcut.action))
        self.table.resizeColumnToContents(0)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.table and event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept(); return True
        return super().eventFilter(watched, event)
