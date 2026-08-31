"""Demonstração isolada do login integrado ao splash.

Não participa do startup oficial, não acessa banco e não armazena senha.
"""

from __future__ import annotations

import random
import sys
from collections.abc import Callable

from PySide6.QtCore import QPointF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)


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
        if not callable(authenticator):
            raise TypeError("A demonstração exige um autenticador explícito.")
        self.authenticator = authenticator
        self.settings = settings or QSettings("NabiCode", "SplashLoginDemo")
        self.system_ready = False
        self.authenticated = False
        self.animation_frames = 0
        self._stars = self._create_stars(180)
        self.setWindowTitle("Demonstração — login integrado ao splash")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMinimumSize(900, 560)
        self.resize(1100, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addStretch(1)
        self.panel = QFrame()
        self.panel.setFixedWidth(430)
        self.panel.setStyleSheet(
            "QFrame{background:rgba(13,17,23,225);border:1px solid #00d084;"
            "border-radius:14px} QLabel{color:#f0f6fc;border:0}"
            "QLineEdit{background:#161b22;color:#f0f6fc;border:1px solid #30363d;"
            "border-radius:7px;padding:10px;font-size:15px}"
            "QPushButton{background:#1f6feb;color:white;border:0;border-radius:7px;"
            "padding:12px;font-weight:800} QCheckBox{color:#c9d1d9;border:0}"
        )
        form = QVBoxLayout(self.panel)
        form.setContentsMargins(30, 25, 30, 25)
        form.setSpacing(10)
        brand = QLabel("NABICODE")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet("font-size:32px;font-weight:900;color:#00e88a;border:0")
        subtitle = QLabel("Entrar enquanto o sistema termina de carregar")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        self.username = QLineEdit(str(self.settings.value("remembered_username", "")))
        self.username.setPlaceholderText("Usuário")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Senha")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember = QCheckBox("Lembrar somente o usuário")
        self.remember.setChecked(bool(self.username.text()))
        self.enter = QPushButton("ENTRAR")
        self.status = QLabel("Carregando componentes…")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        for widget in (
            brand, subtitle, self.username, self.password, self.remember,
            self.enter, self.status,
        ):
            form.addWidget(widget)
        root.addWidget(self.panel, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch(1)

        self.enter.clicked.connect(self.authenticate)
        self.password.returnPressed.connect(self.authenticate)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._animate)
        self.timer.start()
        (self.password if self.username.text() else self.username).setFocus()

    def _create_stars(self, count: int) -> list[list[float]]:
        rng = random.Random(20260830)
        return [
            [rng.random(), rng.random(), rng.uniform(0.4, 1.8), rng.uniform(0.4, 1.0)]
            for _ in range(count)
        ]

    def _animate(self) -> None:
        self.animation_frames += 1
        for star in self._stars:
            star[1] += star[2] / 1400
            if star[1] > 1:
                star[1] = 0
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#05070d"))
        for x, y, speed, light in self._stars:
            color = QColor(80, 190 + int(55 * light), 210, 100 + int(140 * light))
            painter.setPen(QPen(color, max(1.0, speed)))
            painter.drawPoint(QPointF(x * self.width(), y * self.height()))

    def set_system_ready(self, ready: bool = True, error: str = "") -> None:
        self.system_ready = bool(ready) and not error
        if error:
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
            self.status.setText("Informe usuário e senha.")
            return
        try:
            accepted = bool(self.authenticator(username, password))
        except Exception:
            accepted = False
        self.password.clear()
        if not accepted:
            self.authenticated = False
            self.status.setText("Usuário ou senha inválidos.")
            self.password.setFocus()
            return
        self.authenticated = True
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
