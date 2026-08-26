from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QAbstractItemView, QDialog, QPushButton

from commercial.application.cash_application_service import (
    CashApplicationService, CashDetailKind, CashDetailRow, CashDetailSnapshot,
    CashSessionView,
)
from ui_qt.commercial.cash_dialog import CashDetailDialog, CashDialog, CashValueDialog


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


def test_detalhes_tipados_paginam_e_reconciliam_cada_origem():
    backend=Backend()
    backend.session=SimpleNamespace(
        id=9,status="ABERTO",opened_at="25/08/2026 08:00:00",closed_at="",
        opening_balance=Decimal("100"),opened_by="ANA",opening_mode="VALOR_INFORMADO",
    )
    backend.session_summary=lambda _id:dict(
        expected_cash=Decimal("153"),dinheiro=Decimal("20"),pix=Decimal("7"),
        cartao=Decimal("8"),outros=Decimal("0"),recebimentos_dinheiro=Decimal("30"),
        suprimentos=Decimal("5"),sangrias=Decimal("2"),movements=(
            dict(data="25/08/2026 09:00:00",tipo="VENDA DINHEIRO",valor=Decimal("20"),
                 usuario="BIA",observacao="Venda balcão",origem="VENDA #11",documento="",sinal=1),
            dict(data="25/08/2026 09:05:00",tipo="VENDA PIX",valor=Decimal("7"),
                 usuario="BIA",observacao="Venda PIX",origem="VENDA #12",documento="",sinal=1),
            dict(data="25/08/2026 09:10:00",tipo="VENDA CARTAO",valor=Decimal("8"),
                 usuario="CAIO",observacao="Venda cartão",origem="VENDA #13",documento="",sinal=1),
            dict(data="25/08/2026 10:00:00",tipo="RECEBIMENTO DINHEIRO",valor=Decimal("30"),
                 usuario="ANA",observacao="Recebimento",origem="RECEBIMENTO #21",documento="REC-21",sinal=1),
            dict(data="25/08/2026 11:00:00",tipo="SUPRIMENTO",valor=Decimal("5"),
                 usuario="ANA",observacao="Troco",origem="CAIXA #31",documento="",sinal=1),
            dict(data="25/08/2026 12:00:00",tipo="SANGRIA",valor=Decimal("2"),
                 usuario="ANA",observacao="Cofre",origem="CAIXA #32",documento="",sinal=-1),
        ),
    )
    service=CashApplicationService(backend,terminal="PC1",user="ANA")
    expected=service.detail_snapshot("expected")
    first=expected.page(1,page_size=2)
    assert first.page==1 and first.total_pages==3 and len(first.items)==2
    assert expected.card_total==Decimal("153.00")
    assert expected.detail_total==Decimal("153.00") and expected.reconciled is True
    assert expected.period_start=="25/08/2026 08:00:00" and expected.period_end==""
    assert expected.items[0].origin=="ABERTURA DO CAIXA #9"
    assert any(item.document=="REC-21" and item.responsible=="ANA" for item in expected.items)
    assert any(item.amount==Decimal("-2.00") for item in expected.items)
    assert service.detail_snapshot("cash").detail_total==Decimal("20.00")
    assert service.detail_snapshot("pix").detail_total==Decimal("7.00")
    assert service.detail_snapshot("card").detail_total==Decimal("8.00")
    assert service.detail_snapshot("supplies").detail_total==Decimal("5.00")
    withdrawals=service.detail_snapshot("withdrawals")
    assert withdrawals.detail_total==Decimal("2.00")
    assert withdrawals.items[0].direction=="SAÍDA"


def test_detalhe_recusa_catalogo_livre_e_limites_de_pagina():
    service=CashApplicationService(Backend(),terminal="PC1",user="ANA")
    with pytest.raises(ValueError): service.detail_snapshot("comando livre")
    snapshot=service.detail_snapshot("cash")
    with pytest.raises(ValueError): snapshot.page(0)
    with pytest.raises(ValueError): snapshot.page(1,page_size=101)


def test_cards_sao_acessiveis_clicaveis_e_bloqueiam_auto_repeat(app,monkeypatch):
    service=CashApplicationService(Backend(),terminal="PC1",user="ANA")
    dialog=CashDialog(service)
    opened=[]
    monkeypatch.setattr(dialog,"open_detail",lambda key:opened.append(key) or True)
    button=dialog.cards["cash"][1]
    assert isinstance(button,QPushButton)
    assert button.accessibleName()=="Detalhar vendas em dinheiro"
    button.setFocus(); key(button,auto=True); assert opened==[]
    key(button); assert opened==["cash"]
    dialog.close()


def test_todos_os_cards_abrem_o_detalhe_tipado_exato(app):
    captured=[]
    class ImmediateDialog(QDialog):
        def exec(self):return QDialog.DialogCode.Rejected
    def factory(snapshot,parent):
        captured.append(snapshot.kind.value)
        return ImmediateDialog(parent)
    dialog=CashDialog(
        CashApplicationService(Backend(),terminal="PC1",user="ANA"),
        detail_dialog_factory=factory,
    )
    expected=("expected","cash","pix","card","supplies","withdrawals","documented")
    assert tuple(dialog.cards)==expected
    for key_name in expected:
        assert dialog.cards[key_name][1].accessibleName()
        assert dialog.open_detail(key_name) is True
    assert tuple(captured)==expected
    dialog.close()


def test_dialogo_de_detalhe_e_somente_leitura_e_pagina(app):
    rows=tuple(CashDetailRow(
        f"25/08/2026 10:0{index}:00",f"VENDA #{index}","VENDA DINHEIRO",
        Decimal("1"),"ENTRADA","ANA","",f"Item {index}",
    ) for index in range(5))
    snapshot=CashDetailSnapshot(
        CashDetailKind.CASH_SALES,"VENDAS DINHEIRO",1,
        "25/08/2026 08:00:00","",Decimal("5"),Decimal("5"),True,rows,
    )
    dialog=CashDetailDialog(snapshot,page_size=2)
    assert dialog.table.editTriggers()==QAbstractItemView.EditTrigger.NoEditTriggers
    assert "RECONCILIADO" in dialog.reconciliation.text()
    assert dialog.previous_button.isEnabled() is False
    assert dialog.next_button.isEnabled() is True and dialog.table.rowCount()==2
    assert dialog.show_page(2) is True and dialog.table.rowCount()==2
    assert dialog.show_page(3) is True and dialog.table.rowCount()==1
    assert dialog.next_button.isEnabled() is False
    dialog.close()


def test_divergencia_nunca_e_exibida_como_reconciliada(app):
    snapshot=CashDetailSnapshot(
        CashDetailKind.PIX_SALES,"PIX",1,"25/08/2026 08:00:00","",
        Decimal("10"),Decimal("9"),False,(),
    )
    dialog=CashDetailDialog(snapshot)
    assert "NÃO RECONCILIADO" in dialog.reconciliation.text()
    assert "R$ 10,00" in dialog.reconciliation.text()
    assert "R$ 9,00" in dialog.reconciliation.text()
    dialog.close()


def test_janela_principal_tem_controles_windows_e_modal_nao_minimiza(app):
    main=CashDialog(CashApplicationService(Backend(),terminal="PC1",user="ANA"))
    flags=main.windowFlags()
    assert flags & Qt.WindowType.WindowMinimizeButtonHint
    assert flags & Qt.WindowType.WindowMaximizeButtonHint
    assert flags & Qt.WindowType.WindowCloseButtonHint
    modal=CashValueDialog("Teste","Confirmar",lambda *_:None)
    assert not modal.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
    assert not modal.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
    main.close();modal.close()


def test_porta_revalida_sessao_e_usa_ator_atual_antes_da_mutacao():
    backend=Backend();actors=["ANA"];actions=[]
    def actor_provider(action):actions.append(action);return actors[-1]
    service=CashApplicationService(
        backend,terminal="PC1",user="INICIAL",actor_provider=actor_provider
    )
    service.current()
    actors.append("BIA")
    service.register_movement("SUPRIMENTO",Decimal("5"),"troco")
    assert backend.calls[-2]==("movement","PC1","SUPRIMENTO",Decimal("5"),"BIA","troco")
    service.close(Decimal("5"),"conferido")
    assert actions==["view","create","reconcile"]
    denied=CashApplicationService(
        backend,terminal="PC1",user="ANA",
        actor_provider=lambda _action:(_ for _ in ()).throw(PermissionError("sessão expirada")),
    )
    before=tuple(backend.calls)
    with pytest.raises(PermissionError):denied.open(Decimal("10"))
    assert tuple(backend.calls)==before


def test_gui_nao_importa_banco_repositorio_fiscal_ou_ia():
    from pathlib import Path
    source=(Path(__file__).parents[1]/"ui_qt/commercial/cash_dialog.py").read_text().lower()
    for forbidden in ("sqlite3","database","repositories","fiscal","sefaz","assistant_nabi"):
        assert forbidden not in source
