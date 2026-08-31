"""Demonstração isolada do login integrado ao splash.

Não participa do startup oficial, não acessa banco e não armazena senha.
"""

from __future__ import annotations

import time
import sys
from collections.abc import Callable

from PySide6.QtCore import QPropertyAnimation, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QLabel, QLineEdit, QPushButton,
    QGraphicsOpacityEffect, QVBoxLayout, QWidget,
)
from build_tools.demo_original_splash_scene import OriginalSplashScene


class SplashLoginDemo(QWidget):
    """Protótipo: fecha somente quando carga e autenticação terminarem."""

    def __init__(
        self,
        authenticator: Callable[[str, str], bool],
        *,
        settings: QSettings | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 10))
        if not callable(authenticator):
            raise TypeError("A demonstração exige um autenticador explícito.")
        self.authenticator = authenticator
        self.settings = settings or QSettings("NabiCode", "SplashLoginDemo")
        self.system_ready = False
        self.authenticated = False
        self.animation_frames = 0
        self.scene = OriginalSplashScene()
        self._started = time.perf_counter()
        self._last_frame = self._started
        self._elapsed = 0.0
        self._frame_dt = 0.0
        self.login_revealed = False
        self.setWindowTitle("Demonstração — login integrado ao splash")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMinimumSize(900, 560)
        self.resize(1100, 680)

        self.panel = QFrame(self)
        self.panel.setStyleSheet(
            "QFrame{background:transparent;border:0} QLabel{color:#f0f6fc;border:0}"
            "QLineEdit{background:rgba(8,16,25,65);color:#f0f6fc;"
            "border:1px solid rgba(180,220,235,90);border-radius:5px;padding:8px;font-size:14px}"
            "QLineEdit:focus{border:1px solid #a0dace}"
            "QPushButton{background:rgba(25,60,65,100);color:white;"
            "border:1px solid rgba(180,220,235,80);border-radius:5px;padding:8px}"
        )
        form = QVBoxLayout(self.panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        form.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.username = QLineEdit(str(self.settings.value("remembered_username", "")))
        self.username.setPlaceholderText("Usuário")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Senha")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember = QCheckBox("Lembrar somente o usuário")
        self.remember.setParent(self.panel)
        self.remember.hide()
        self.remember.setChecked(bool(self.username.text()))
        self.enter = QPushButton("ENTRAR")
        self.status = QLabel("Carregando componentes…")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        for widget in (
            self.username, self.password,
            self.enter, self.status,
        ):
            form.addWidget(widget)
        self.status.hide()
        self.panel.hide()
        self.opacity = QGraphicsOpacityEffect(self.panel)
        self.panel.setGraphicsEffect(self.opacity)
        self.opacity.setOpacity(0)
        self.reveal = QPropertyAnimation(self.opacity, b"opacity", self)
        self.reveal.setDuration(800)
        self.reveal.setStartValue(0.0)
        self.reveal.setEndValue(1.0)

        self.enter.clicked.connect(self.authenticate)
        self.password.returnPressed.connect(self.authenticate)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._animate)
        self.timer.start()
        (self.password if self.username.text() else self.username).setFocus()

    def _animate(self) -> None:
        self.animation_frames += 1
        now = time.perf_counter()
        self._frame_dt = min(0.1, now - self._last_frame)
        self._last_frame = now
        self._elapsed = now - self._started
        self._reveal_login(self._elapsed)
        self.update()

    def _reveal_login(self, elapsed):
        if elapsed >= 8.8 and not self.login_revealed:
            self.login_revealed = True
            self._place_panel()
            self.panel.show()
            self.reveal.start()
            (self.password if self.username.text() else self.username).setFocus()

    def _place_panel(self):
        scale = min(self.width() / 1280, self.height() / 720)
        width = min(340, self.width() - 40)
        top = (self.height() - 720 * scale) / 2 + 430 * scale
        self.panel.setGeometry(int((self.width() - width) / 2), int(top), width, 190)

    def resizeEvent(self, event):
        self._place_panel()
        super().resizeEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000105"))
        raw = self.scene.render(self._elapsed, self._frame_dt)
        frame = QImage(raw, 1280, 720, 1280 * 3, QImage.Format.Format_RGB888)
        scale = min(self.width() / 1280, self.height() / 720)
        painter.drawImage(QRectF((self.width() - 1280 * scale) / 2,
                                (self.height() - 720 * scale) / 2,
                                1280 * scale, 720 * scale), frame)

    def closeEvent(self, event):
        self.timer.stop()
        self.reveal.stop()
        super().closeEvent(event)

    def set_system_ready(self, ready: bool = True, error: str = "") -> None:
        self.system_ready = bool(ready) and not error
        if error:
            self.status.show()
            self.status.setText(f"Falha no carregamento: {error}")
        elif self.authenticated and self.system_ready:
            self.status.setText("Pronto. Abrindo o NabiCode…")
        elif self.system_ready:
            self.status.setText("Sistema pronto. Aguardando o login.")
        self._finish_if_ready()

    def authenticate(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            self.status.show()
            self.status.setText("Informe usuário e senha.")
            return
        try:
            accepted = bool(self.authenticator(username, password))
        except Exception:
            accepted = False
        self.password.clear()
        if not accepted:
            self.status.show()
            self.authenticated = False
            self.status.setText("Usuário ou senha inválidos.")
            self.password.setFocus()
            return
        self.authenticated = True
        self.status.show()
        if self.remember.isChecked():
            self.settings.setValue("remembered_username", username)
        else:
            self.settings.remove("remembered_username")
        self.settings.sync()
        self.status.setText(
            "Login aceito. Finalizando o carregamento…"
            if not self.system_ready else "Pronto. Abrindo o NabiCode…"
        )
        self._finish_if_ready()

    def _finish_if_ready(self) -> None:
        if self.system_ready and self.authenticated:
            self.timer.stop()
            self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)


def run_demo() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    demo = SplashLoginDemo(lambda user, password: bool(user and password))
    demo.show()
    QTimer.singleShot(4500, demo.set_system_ready)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_demo())
