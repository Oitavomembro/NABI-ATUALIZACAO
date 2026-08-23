from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from commercial.application.cash_application_service import CashApplicationService, CashSessionView
from ui_qt.commercial.cash_dialog import CashDialog, CashValueDialog


class Backend:
    def __init__(self): self.calls=[]; self.session=None
    def get_open_session(self, terminal): self.calls.append(("get", terminal)); return self.session
    def open_session(self, terminal,user,value,mode):
        self.calls.append(("open",terminal,user,value,mode)); self.session=SimpleNamespace(id=1,status="ABERTO")
    def session_summary(self, _id):
        return dict(expected_cash=Decimal("110"),dinheiro=Decimal("10"),pix=Decimal("20"),
                    cartao=Decimal("30"),outros=Decimal("0"),recebimentos_dinheiro=Decimal("0"),
                    suprimentos=Decimal("5"),sangrias=Decimal("2"),movements=[])
    def register_session_movement(self,*args): self.calls.append(("movement",)+args)
    def close_session(self,*args): self.calls.append(("close",)+args); self.session=None; return SimpleNamespace(status="FECHADO")
    def history(self, terminal): return []


@pytest.fixture(scope="module")
def app(): return QApplication.instance() or QApplication([])


def key(widget, auto=False, shift=False):
    QApplication.sendEvent(widget,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,"",auto,1))


def test_porta_fixa_terminal_usuario_e_retorna_resumo_tipado():
    backend=Backend(); service=CashApplicationService(backend,terminal="PC1",user="ANA")
    assert not service.current().is_open
    state=service.open(Decimal("100"),informed=True)
    assert state.is_open and state.expected_cash==Decimal("110.00")
    assert backend.calls[-2]==("open","PC1","ANA",Decimal("100"),"VALOR_INFORMADO")
    service.register_movement("SANGRIA",Decimal("5"),"cofre")
    assert backend.calls[-2][0]=="movement"
    service.close(Decimal("110"),"")
    assert backend.calls[-1][0]=="close"


def test_dialog_reflete_estado_e_nao_persiste_diretamente(app):
    backend=Backend(); service=CashApplicationService(backend,terminal="PC1",user="ANA")
    dialog=CashDialog(service); assert dialog.status.text()=="CAIXA FECHADO"
    dialog.open_without_value(); assert dialog.status.text()=="CAIXA ABERTO"
    assert not dialog.open_button.isEnabled() and dialog.close_button.isEnabled(); dialog.close()


def test_enter_shift_e_auto_repeat_sao_deterministicos(app):
    calls=[]; dialog=CashValueDialog("Teste","Confirmar",lambda amount,note:calls.append((amount,note)))
    dialog.show(); app.processEvents(); dialog.amount.setFocus()
    key(dialog.amount,auto=True); assert calls==[] and dialog.amount.hasFocus()
    key(dialog.amount); assert dialog.note.hasFocus()
    key(dialog.note,shift=True); assert dialog.amount.hasFocus()
    dialog.confirm.setFocus(); key(dialog.confirm); assert len(calls)==1


def test_gui_nao_importa_banco_repositorio_fiscal_ou_ia():
    from pathlib import Path
    source=(Path(__file__).parents[1]/"ui_qt/commercial/cash_dialog.py").read_text().lower()
    for forbidden in ("sqlite3","database","repositories","fiscal","sefaz","assistant_nabi"):
        assert forbidden not in source
