from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.context_help import ContextHelpRegistry


STYLE = """
QDialog { background:#0d1117;color:#f0f6fc;font-size:14px; }
QLabel { color:#f0f6fc; } QLineEdit,QComboBox,QTableWidget { background:#161b22;
 color:#f0f6fc;border:1px solid #30363d;min-height:30px; }
QHeaderView::section { background:#21262d;color:#f0f6fc;padding:7px;font-weight:800; }
QPushButton { background:#21262d;color:#f0f6fc;border:1px solid #30363d;
 border-radius:7px;min-height:34px;padding:4px 12px;font-weight:700; }
QPushButton:focus { border:2px solid #58a6ff; }
"""


class HelpDialog(QDialog):
    """Apresentação Qt somente leitura do catálogo de ajuda do Legacy."""

    def __init__(self, registry=None, parent=None, *, context="global"):
        super().__init__(parent)
        self.registry = registry or ContextHelpRegistry()
        self.setWindowTitle("Central de Ajuda NabiCode")
        self.resize(820, 600); self.setMinimumSize(660, 460); self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("CENTRAL DE AJUDA"); title.setStyleSheet("font-size:24px;font-weight:900;color:#00d084")
        root.addWidget(title)
        row = QHBoxLayout(); self.topic = QComboBox(); self.search = QLineEdit(); self.search.setPlaceholderText("Pesquisar tecla ou ação")
        row.addWidget(QLabel("Assunto")); row.addWidget(self.topic, 1); row.addWidget(self.search, 2); root.addLayout(row)
        self.description = QLabel(); self.description.setWordWrap(True); self.description.setStyleSheet("color:#c9d1d9")
        root.addWidget(self.description)
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(("Tecla", "Ação")); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.installEventFilter(self); root.addWidget(self.table, 1)
        self.notes = QLabel(); self.notes.setWordWrap(True); self.notes.setStyleSheet("color:#8b949e"); root.addWidget(self.notes)
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
