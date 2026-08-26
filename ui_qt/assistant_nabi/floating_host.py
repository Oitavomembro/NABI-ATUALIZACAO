from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class NabiFloatingAssistant(QWidget):
    """Mascote arrastável que revela o painel sem ampliar suas capacidades."""

    COLLAPSED_SIZE = QSize(104, 116)
    EXPANDED_WIDTH = 460
    POSITION_KEY = "ui/nabi_floating/position"
    DRAG_THRESHOLD = 7

    def __init__(self, panel: QWidget, parent: QWidget, *, settings: QSettings | None = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._settings = settings or QSettings()
        self._expanded = False
        self._drag_origin: QPoint | None = None
        self._widget_origin: QPoint | None = None
        self._dragging = False
        self.setObjectName("nabiFloatingAssistant")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        self.launcher = QPushButton(objectName="nabiFloatingLauncher")
        self.launcher.setAccessibleName("Abrir conversa com a Nabi")
        self.launcher.setToolTip("Nabi disponível — clique para conversar; arraste para mover")
        self.launcher.setFixedSize(96, 96)
        self.launcher.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.launcher.installEventFilter(self)
        # Mantém a API semântica do QPushButton para acessibilidade/testes; os
        # eventos físicos consumidos pelo filtro não emitem este sinal.
        self.launcher.clicked.connect(self.toggle)
        self._load_mascot()
        launcher_row.addWidget(self.launcher)
        root.addLayout(launcher_row)
        self.setStyleSheet("""
            QWidget#nabiFloatingAssistant { background: transparent; }
            QFrame#nabiConversationBubble { background:#101923;border:2px solid #00dfff;
                border-bottom:6px solid #006f91;border-radius:18px; }
            QPushButton#nabiFloatingLauncher { background:#09131d;border:3px solid #00e5ff;
                border-bottom:7px solid #006b8c;border-radius:46px;padding:7px; }
            QPushButton#nabiFloatingLauncher:hover { border:4px solid #7df6ff;background:#102c3b; }
            QPushButton#nabiFloatingLauncher:pressed { border-bottom:3px solid #006b8c;padding-top:11px; }
            QPushButton { color:#f0f6fc;background:#162331;border:1px solid #31516a;
                border-radius:8px;min-height:34px;font-weight:800;padding:0 10px; }
            QPushButton:focus { border:2px solid #ffffff; }
        """)
        parent.installEventFilter(self)
        self.bubble.hide()
        self.setFixedSize(self.COLLAPSED_SIZE)
        self.show()
        self.raise_()
        QTimer.singleShot(0, self.restore_position)

    def widget(self) -> QWidget:
        return self._panel

    def isExpanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self.collapse() if self._expanded else self.expand()

    def expand(self) -> None:
        parent = self.parentWidget()
        available_height = max(500, (parent.height() if parent else 760) - 90)
        self._expanded = True
        self.bubble.show()
        self.setFixedSize(self.EXPANDED_WIDTH, min(720, available_height))
        self.launcher.setAccessibleName("Recolher conversa com a Nabi")
        self.clamp_to_parent()
        self.raise_()
        message = getattr(self._panel, "message", None)
        if message is not None:
            message.setFocus(Qt.FocusReason.OtherFocusReason)

    def collapse(self) -> None:
        self._expanded = False
        self.bubble.hide()
        self.setFixedSize(self.COLLAPSED_SIZE)
        self.launcher.setAccessibleName("Abrir conversa com a Nabi")
        self.clamp_to_parent()
        self.raise_()

    def attach_to(self, parent: QWidget) -> None:
        previous = self.parentWidget()
        if previous is not parent:
            if previous is not None:
                previous.removeEventFilter(self)
            self.setParent(parent)
            parent.installEventFilter(self)
        self.show()
        self.clamp_to_parent()
        self.raise_()

    def restore_position(self) -> None:
        saved = self._settings.value(self.POSITION_KEY)
        if isinstance(saved, QPoint):
            self.move(saved)
        else:
            self._place_default()
        self.clamp_to_parent()

    def save_position(self) -> None:
        self._settings.setValue(self.POSITION_KEY, self.pos())
        self._settings.sync()

    def clamp_to_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = 8
        maximum_x = max(margin, parent.contentsRect().width() - self.width() - margin)
        maximum_y = max(margin, parent.contentsRect().height() - self.height() - margin)
        self.move(min(max(margin, self.x()), maximum_x), min(max(margin, self.y()), maximum_y))

    def eventFilter(self, watched, event) -> bool:
        if watched is getattr(self, "launcher", None) and isinstance(event, QMouseEvent):
            return self._filter_launcher_mouse(event)
        if watched is self.parentWidget() and event.type() in {
            QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Move,
            QEvent.Type.ScreenChangeInternal,
        }:
            QTimer.singleShot(0, self.clamp_to_parent)
        return super().eventFilter(watched, event)

    def _filter_launcher_mouse(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton and event.type() != QEvent.Type.MouseMove:
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            self._drag_origin = event.globalPosition().toPoint()
            self._widget_origin = self.pos()
            self._dragging = False
            return True
        if event.type() == QEvent.Type.MouseMove and self._drag_origin is not None:
            delta = event.globalPosition().toPoint() - self._drag_origin
            if delta.manhattanLength() >= self.DRAG_THRESHOLD:
                self._dragging = True
                self.move((self._widget_origin or self.pos()) + delta)
                self.clamp_to_parent()
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and self._drag_origin is not None:
            was_drag = self._dragging
            self._drag_origin = self._widget_origin = None
            self._dragging = False
            if was_drag:
                self.save_position()
            else:
                self.toggle()
            return True
        return False

    def _place_default(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.move(max(22, parent.width() - self.width() - 22),
                      max(22, parent.height() - self.height() - 22))

    def _load_mascot(self) -> None:
        asset = Path(__file__).resolve().parent / "assets" / "nabi_mascot_blue_v2_transparent.png"
        pixmap = QPixmap(str(asset))
        if pixmap.isNull():
            self.launcher.setText("N")
            self.launcher.setStyleSheet("font-size:34px;font-weight:900;color:#7df6ff")
            return
        self.launcher.setIcon(QIcon(pixmap))
        self.launcher.setIconSize(QSize(74, 74))
