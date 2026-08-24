from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout,
)

LOGIN_STYLE = """
QDialog { background:#0d1117; color:#f0f6fc; }
QFrame#loginCard { background:#161b22; border:1px solid #30363d; border-radius:18px; }
QLabel { color:#f0f6fc; }
QLineEdit { background:#0d1117; color:#f0f6fc; border:1px solid #30363d;
 border-radius:9px; min-height:48px; padding:0 14px; font-size:16px; }
QLineEdit:focus { border:2px solid #1f6feb; }
QPushButton { border:0; border-radius:9px; min-height:48px; padding:0 18px;
 color:#ffffff; font-size:15px; font-weight:800; }
QPushButton:focus { border:3px solid #ffffff; }
"""


class ApplicationLoginDialog(QDialog):
    """Login amplo com o fluxo do Legacy e a segurança atual preservada."""

    def __init__(self, security, parent=None):
        super().__init__(parent)
        self.security = security
        self.setWindowTitle("Entrar no NabiCode")
        self.setModal(True)
        self.resize(760, 500)
        self.setMinimumSize(680, 440)
        self.setStyleSheet(LOGIN_STYLE)
        outer = QVBoxLayout(self); outer.setContentsMargins(54, 42, 54, 42)
        card = QFrame(objectName="loginCard"); outer.addWidget(card)
        root = QVBoxLayout(card); root.setContentsMargins(48, 36, 48, 36); root.setSpacing(12)
        brand = QLabel("NABI  CODE"); brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet("color:#00d084;font-size:30px;font-weight:900"); root.addWidget(brand)
        title = QLabel("ENTRAR NO NABICODE"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:21px;font-weight:900"); root.addWidget(title)
        guidance = QLabel("Informe seu usuário e senha para acessar o sistema.")
        guidance.setAlignment(Qt.AlignmentFlag.AlignCenter)
        guidance.setStyleSheet("color:#8b949e;font-size:14px"); root.addWidget(guidance)
        root.addWidget(QLabel("Usuário")); self.username = QLineEdit()
        self.username.setPlaceholderText("Digite seu usuário"); self.username.setAccessibleName("Usuário")
        root.addWidget(self.username); root.addWidget(QLabel("Senha")); self.password = QLineEdit()
        self.password.setPlaceholderText("Digite sua senha"); self.password.setAccessibleName("Senha")
        self.password.setEchoMode(QLineEdit.EchoMode.Password); root.addWidget(self.password)
        actions = QHBoxLayout(); self.cancel = QPushButton("Cancelar  [Esc]")
        self.cancel.setStyleSheet("background:#30363d"); self.cancel.clicked.connect(self.reject)
        self.enter = QPushButton("Entrar  [Enter]"); self.enter.setStyleSheet("background:#1f6feb")
        self.enter.clicked.connect(self.authenticate); actions.addWidget(self.cancel); actions.addWidget(self.enter, 1)
        root.addLayout(actions); self.fields = (self.username, self.password, self.enter)
        for field in self.fields: field.installEventFilter(self)
        self.username.setFocus()

    def eventFilter(self, watched, event):
        if watched in self.fields and event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            if event.isAutoRepeat(): return True
            index = self.fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: self.fields[max(0, index - 1)].setFocus()
            elif watched is self.enter: self.authenticate()
            else: self.fields[index + 1].setFocus()
            return True
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            event.accept()
            if not event.isAutoRepeat(): self.reject()
            return True
        return super().eventFilter(watched, event)

    def authenticate(self):
        session = self.security.authenticate(self.username.text(), self.password.text())
        self.password.clear()
        if session is None:
            QMessageBox.warning(self, "Acesso negado", "Usuário ou senha inválidos.")
            self.password.setFocus(); return
        self.accept()
