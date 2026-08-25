from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout,
)
ADMIN_METALLIC_STYLE = """
QDialog { background:#111418; color:#edf0f2; }
QFrame#loginCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #30353a,stop:0.03 #1c2024,stop:1 #101317); border:1px solid #626970; border-radius:18px; }
QLabel { color:#e8ebee; }
QLineEdit,QComboBox,QDateEdit,QSpinBox,QTextEdit,QPlainTextEdit,QTableWidget { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #292e33,stop:1 #171a1e); color:#f4f6f7; border:1px solid #555d65; border-radius:7px; padding:6px; selection-background-color:#386b7b; selection-color:#fff; }
QLineEdit:focus,QComboBox:focus,QDateEdit:focus,QSpinBox:focus,QTextEdit:focus,QPlainTextEdit:focus,QTableWidget:focus { border:1px solid #73c7dc; }
QPushButton { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #626a72,stop:0.45 #41474d,stop:1 #272c31); color:#f6f7f8; border:1px solid #7a838b; border-radius:7px; min-height:34px; padding:4px 14px; font-weight:700; }
QPushButton:hover { border-color:#a8b0b7; background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #737c84,stop:1 #343a40); }
QPushButton:focus { border:2px solid #73c7dc; }
QPushButton:disabled { color:#7f878e; background:#25292d; border-color:#3c4248; }
QPushButton#primary { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #567984,stop:1 #294852); border-color:#73c7dc; }
QPushButton#destructive { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #a13b42,stop:1 #53191e); border-color:#d65b63; }
QHeaderView::section { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #555d65,stop:1 #292e33); color:#fff; border:0; border-right:1px solid #687078; border-bottom:1px solid #73c7dc; padding:7px; font-weight:800; }
QTableWidget { gridline-color:#3e454c; alternate-background-color:#20252a; }
QTabWidget::pane { border:1px solid #555d65; border-top:1px solid #73c7dc; background:#171b1f; }
QTabBar::tab { background:#292e33; color:#cbd0d4; border:1px solid #4b5259; padding:9px 14px; }
QTabBar::tab:selected { background:#4a5158; color:#fff; border-bottom:2px solid #73c7dc; }
QScrollBar:vertical { background:#171a1e; width:12px; }
QScrollBar::handle:vertical { background:#596169; border-radius:5px; min-height:24px; }
"""
LOGIN_STYLE = ADMIN_METALLIC_STYLE + "QLineEdit,QPushButton { min-height:48px; font-size:16px; }"


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
        brand.setStyleSheet("color:#e4e8eb;font-size:30px;font-weight:900;border-bottom:1px solid #73c7dc"); root.addWidget(brand)
        title = QLabel("ENTRAR NO NABICODE"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:21px;font-weight:900"); root.addWidget(title)
        guidance = QLabel("Informe seu usuário e senha para acessar o sistema.")
        guidance.setAlignment(Qt.AlignmentFlag.AlignCenter)
        guidance.setStyleSheet("color:#aeb5bb;font-size:14px"); root.addWidget(guidance)
        root.addWidget(QLabel("Usuário")); self.username = QLineEdit()
        self.username.setPlaceholderText("Digite seu usuário"); self.username.setAccessibleName("Usuário")
        root.addWidget(self.username); root.addWidget(QLabel("Senha")); self.password = QLineEdit()
        self.password.setPlaceholderText("Digite sua senha"); self.password.setAccessibleName("Senha")
        self.password.setEchoMode(QLineEdit.EchoMode.Password); root.addWidget(self.password)
        actions = QHBoxLayout(); self.cancel = QPushButton("Cancelar  [Esc]")
        self.cancel.clicked.connect(self.reject)
        self.enter = QPushButton("Entrar  [Enter]"); self.enter.setObjectName("primary")
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
