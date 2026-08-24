import ast
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtCore import QEvent,Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from ui_qt.administration.audit_dialog import AuditDialog

APP=QApplication.instance() or QApplication([])


class Application:
    def __init__(self): self.calls=[]
    def load(self,*,limit):
        self.calls.append(limit)
        entries=(SimpleNamespace(date="24/08/2026",user="admin",action="LOGIN",result="SUCESSO",details="Acesso autorizado"),SimpleNamespace(date="24/08/2026",user="maria",action="LOGIN",result="NEGADO",details="Senha inválida"))
        return SimpleNamespace(entries=entries,limit=limit)


def test_carrega_limite_e_filtra_sem_nova_consulta():
    application=Application(); dialog=AuditDialog(application)
    assert application.calls==[500] and dialog.table.rowCount()==2
    dialog.search.setText("maria")
    assert application.calls==[500] and dialog.table.rowCount()==1
    assert dialog.table.item(0,1).text()=="maria"
    dialog.close()


def test_enter_na_tabela_nao_executa_acao():
    dialog=AuditDialog(Application())
    for repeat in (False,True):
        event=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",repeat,1)
        assert dialog.eventFilter(dialog.table,event) is True
    dialog.close()


def test_gui_nao_importa_banco_fiscal_ou_legacy():
    source=Path(__file__).parents[1].joinpath("ui_qt/administration/audit_dialog.py").read_text(encoding="utf-8")
    modules=[]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Import): modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node,ast.ImportFrom): modules.append(str(node.module or "").lower())
    for forbidden in ("sqlite3","database","repositories","fiscal","sefaz","nabicode_legacy"):
        assert not any(forbidden in module for module in modules)
