from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent,Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
from commercial.application.financial_dto import FinancialSummary,ReceivableSummary,PayableSummary
from ui_qt.commercial.financial_dialog import FinancialDialog,SettlementDialog,TitleEditorDialog

def rec():return ReceivableSummary(7,3,"CLIENTE","MANUAL","","DOC","TESTE",Decimal("100"),Decimal("0"),Decimal("100"),date.today(),date.today(),"ABERTO",False)
def pay():return PayableSummary(8,None,"FORNECEDOR","MANUAL","","NF","CONTA",Decimal("50"),Decimal("0"),Decimal("50"),date.today(),date.today(),"ABERTO",False)
class Query:
 def receivables(self):return (rec(),)
 def payables(self):return (pay(),)
 def financial_summary(self,*_):return FinancialSummary(Decimal("100"),Decimal("0"),Decimal("50"),Decimal("50"),Decimal("0"),Decimal("0"))
class Actions:
 def __init__(self):self.calls=[]
 def create_receivable(self,c,**k):self.calls.append(("create_r",c,k));return SimpleNamespace(committed=True,message="ok")
 def create_payable(self,c,**k):self.calls.append(("create_p",c,k));return SimpleNamespace(committed=True,message="ok")
 def settle_receivable(self,c,**k):self.calls.append(("settle_r",c,k));return SimpleNamespace(committed=True,message="ok")
 def settle_payable(self,c,**k):self.calls.append(("settle_p",c,k));return SimpleNamespace(committed=True,message="ok")
@pytest.fixture(scope="module")
def app():return QApplication.instance() or QApplication([])
def test_lista_ids_reais_resumo_e_separacao(app):
 d=FinancialDialog(Query(),Actions(),user="ANA");assert d.receivable_table.item(0,0).data(Qt.ItemDataRole.UserRole)==7;assert "R$ 100,00" in d.summary.text();d.tabs.setCurrentIndex(1);assert d._selected().title_id==8;d.close()
def test_enter_auto_repeat_nao_baixa_e_enter_simples_uma_vez(app,monkeypatch):
 d=FinancialDialog(Query(),Actions(),user="ANA");calls=[];monkeypatch.setattr(d,"settle",lambda:calls.append(1));d.show();app.processEvents();QApplication.sendEvent(d.receivable_table,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",True,1));assert calls==[];QApplication.sendEvent(d.receivable_table,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier));assert calls==[1];d.close()
def test_criacao_so_executa_apos_confirmacao_explicita(app,monkeypatch):
 calls=[];dialog=TitleEditorDialog("RECEBER",lambda c:calls.append(c) or SimpleNamespace(committed=True,message="ok"));dialog.amount.set_value("10");monkeypatch.setattr(QMessageBox,"question",lambda *_:QMessageBox.StandardButton.No);dialog._confirm();assert calls==[];monkeypatch.setattr(QMessageBox,"question",lambda *_:QMessageBox.StandardButton.Yes);dialog._confirm();assert len(calls)==1 and dialog.result()==QDialog.DialogCode.Accepted
def test_gui_sem_banco_fiscal_ia():
 from pathlib import Path
 source=(Path(__file__).parents[1]/"ui_qt/commercial/financial_dialog.py").read_text().lower()
 for forbidden in ("sqlite3","database","repositories","fiscal","sefaz","assistant_nabi"):assert forbidden not in source

def test_janela_principal_tem_controles_windows_e_dialogos_permanecem_modais(app):
 d=FinancialDialog(Query(),Actions(),user="ANA")
 flags=d.windowFlags()
 assert flags & Qt.WindowType.WindowMinimizeButtonHint
 assert flags & Qt.WindowType.WindowMaximizeButtonHint
 assert flags & Qt.WindowType.WindowCloseButtonHint
 editor=TitleEditorDialog("RECEBER",lambda _command:None)
 settlement=SettlementDialog(rec(),"RECEBER",lambda _command:None)
 for modal in (editor,settlement):
  assert modal.isModal() is True
  assert not modal.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
  assert not modal.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
  modal.close()
 d.close()

def test_financeiro_revalida_permissao_e_ator_por_acao(app):
 calls=[]
 actor=["ANA"]
 def guard(action):calls.append(action);return actor[-1]
 d=FinancialDialog(Query(),Actions(),user="INICIAL",access_guard=guard)
 assert calls[0]=="view"
 actor.append("BIA")
 context=d._context("pay")
 assert context.requested_by=="BIA" and calls[-1]=="pay"
 d.access_guard=lambda _action:(_ for _ in ()).throw(PermissionError("negado"))
 with pytest.raises(PermissionError):d._context("create")
 d.close()
