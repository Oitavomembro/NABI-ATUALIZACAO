from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


class NabiFloatingAssistant(QWidget):
    """Mascote flutuante que revela o painel escrito somente quando solicitado."""

    COLLAPSED_SIZE = QSize(104, 116)
    EXPANDED_WIDTH = 460

    def __init__(self, panel: QWidget, parent: QWidget) -> None:
        super().__init__(parent)
        self._panel = panel
        self._expanded = False
        self.setObjectName("nabiFloatingAssistant")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAccessibleName("Nabi — assistente flutuante")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.bubble = QFrame(objectName="nabiConversationBubble")
        bubble_layout = QVBoxLayout(self.bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 12)
        bubble_layout.setSpacing(8)
        heading = QHBoxLayout()
        title = QLabel("NABI  •  CANAL LOCAL")
        title.setStyleSheet("color:#72eaff;font-size:13px;font-weight:900;letter-spacing:1px")
        self.collapse_button = QPushButton("Recolher")
        self.collapse_button.setAccessibleName("Recolher conversa da Nabi")
        self.collapse_button.clicked.connect(self.collapse)
        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(self.collapse_button)
        bubble_layout.addLayout(heading)
        panel.setParent(self.bubble)
        bubble_layout.addWidget(panel, 1)
        root.addWidget(self.bubble, 1)

        launcher_row = QHBoxLayout()
        launcher_row.addStretch()
        self.launcher = QPushButton()
        self.launcher.setObjectName("nabiFloatingLauncher")
        self.launcher.setAccessibleName("Abrir conversa com a Nabi")
        self.launcher.setToolTip("Nabi disponível — clique para conversar")
        self.launcher.setFixedSize(96, 96)
        self.launcher.clicked.connect(self.toggle)
        self._load_mascot()
        launcher_row.addWidget(self.launcher)
        root.addLayout(launcher_row)

        self.setStyleSheet("""
            QWidget#nabiFloatingAssistant { background: transparent; }
            QFrame#nabiConversationBubble {
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #1c2a38,stop:0.12 #101923,stop:1 #070c12);
                border:2px solid #00dfff;
                border-bottom:6px solid #006f91;
                border-radius:18px;
            }
            QPushButton#nabiFloatingLauncher {
                background:qradialgradient(cx:0.5,cy:0.5,radius:0.65,
                    stop:0 #16384a,stop:0.72 #09131d,stop:1 #02070b);
                border:3px solid #00e5ff;
                border-bottom:7px solid #006b8c;
                border-radius:46px;
                padding:7px;
            }
            QPushButton#nabiFloatingLauncher:hover {
                border:4px solid #7df6ff;
                background:#102c3b;
            }
            QPushButton#nabiFloatingLauncher:pressed {
                border-bottom:3px solid #006b8c;
                padding-top:11px;
            }
            QPushButton { color:#f0f6fc;background:#162331;border:1px solid #31516a;
                border-radius:8px;min-height:34px;font-weight:800;padding:0 10px; }
            QPushButton:focus { border:2px solid #ffffff; }
        """)

        parent.installEventFilter(self)
        self.bubble.hide()
        self.setFixedSize(self.COLLAPSED_SIZE)
        self.show()
        self.raise_()
        QTimer.singleShot(0, self._place)

    def widget(self) -> QWidget:
        """Retorna o painel funcional interno sem expor um dock acoplado."""

        return self._panel

    def isExpanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self) -> None:
        parent = self.parentWidget()
        available_height = max(500, (parent.height() if parent else 760) - 90)
        self._expanded = True
        self.bubble.show()
        self.setFixedSize(self.EXPANDED_WIDTH, min(720, available_height))
        self.launcher.setAccessibleName("Recolher conversa com a Nabi")
        self._place()
        self.raise_()
        message = getattr(self._panel, "message", None)
        if message is not None:
            message.setFocus(Qt.FocusReason.OtherFocusReason)

    def collapse(self) -> None:
        self._expanded = False
        self.bubble.hide()
        self.setFixedSize(self.COLLAPSED_SIZE)
        self.launcher.setAccessibleName("Abrir conversa com a Nabi")
        self._place()
        self.raise_()
        self.launcher.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.parentWidget() and event.type() in {
            QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Move,
        }:
            QTimer.singleShot(0, self._place)
        return super().eventFilter(watched, event)

    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = 22
        self.move(
            max(margin, parent.width() - self.width() - margin),
            max(margin, parent.height() - self.height() - margin),
        )

    def _load_mascot(self) -> None:
        asset = (
            Path(__file__).resolve().parent
            / "assets"
            / "nabi_mascot_blue_v2_transparent.png"
        )
        pixmap = QPixmap(str(asset))
        if pixmap.isNull():
            self.launcher.setText("N")
            self.launcher.setStyleSheet("font-size:34px;font-weight:900;color:#7df6ff")
            return
        self.launcher.setIcon(QIcon(pixmap))
        self.launcher.setIconSize(QSize(74, 74))

