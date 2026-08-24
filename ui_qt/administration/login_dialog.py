from PySide6.QtCore import QEvent,Qt
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QFormLayout,QLabel,QLineEdit,QMessageBox,QVBoxLayout

class ApplicationLoginDialog(QDialog):
    def __init__(self,security,parent=None):
        super().__init__(parent);self.security=security;self.setWindowTitle("Entrar no NabiCode");self.setModal(True);self.setMinimumWidth(460)
        root=QVBoxLayout(self);root.addWidget(QLabel("Informe seu usuário e senha para acessar os módulos do NabiCode."));form=QFormLayout();self.username=QLineEdit();self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);form.addRow("Usuário",self.username);form.addRow("Senha",self.password);root.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);self.enter=buttons.button(QDialogButtonBox.StandardButton.Ok);self.enter.setText("Entrar");buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar");buttons.accepted.connect(self.authenticate);buttons.rejected.connect(self.reject);root.addWidget(buttons);self.fields=(self.username,self.password,self.enter)
        for field in self.fields:field.installEventFilter(self)
        self.username.setFocus()
    def eventFilter(self,w,e):
        if w in self.fields and e.type()==QEvent.Type.KeyPress and e.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter}:
            e.accept()
            if e.isAutoRepeat():return True
            i=self.fields.index(w)
            if e.modifiers()&Qt.KeyboardModifier.ShiftModifier:self.fields[max(0,i-1)].setFocus()
            elif w is self.enter:self.authenticate()
            else:self.fields[i+1].setFocus()
            return True
        return super().eventFilter(w,e)
    def authenticate(self):
        session=self.security.authenticate(self.username.text(),self.password.text())
        self.password.clear()
        if session is None:QMessageBox.warning(self,"Acesso negado","Usuário ou senha inválidos.");self.password.setFocus();return
        self.accept()
