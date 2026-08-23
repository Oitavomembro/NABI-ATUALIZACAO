from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from commercial.application.customer_dto import CustomerDetails
from fichario.pdv_view_model import FicharioPDVViewModel
from fichario.receipt_dialog import CustomerReceiptDialog
from ui_qt.commercial.customer_dialog import CustomerEditorDialog, CustomerManagementDialog


def details(balance=Decimal("50")):
    return CustomerDetails(
        7, "C7", 7007, "MARIA", "", "", "71999990000", "RUA A", "",
        Decimal("500"), balance, Decimal("500") - balance,
    )


class CustomerService:
    def __init__(self): self.balance = Decimal("50")
    def list_customers(self, term="", limit=500): return (details(self.balance),)
    def get_customer(self, customer_id):
        assert customer_id == 7; return details(self.balance)
    def next_record_number(self): return 5500


class Actions:
    def __init__(self, service): self.service = service; self.calls = []
    def receive_customer_payment(self, command, *, context, confirmation_granted):
        self.calls.append((command, context, confirmation_granted))
        self.service.balance -= command.amount
        return SimpleNamespace(committed=True, resource_id=91, message="confirmado")


@pytest.fixture(scope="module")
def app(): return QApplication.instance() or QApplication([])


def key(widget, modifiers=Qt.KeyboardModifier.NoModifier, auto=False):
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, modifiers, "", auto, 1)
    QApplication.sendEvent(widget, event)


def test_recebimento_transporta_id_real_e_exige_confirmacao_explicita(app, monkeypatch):
    service = CustomerService(); actions = Actions(service)
    dialog = CustomerReceiptDialog(service, actions, "operador")
    dialog.amount.set_value(Decimal("20"))
    key(dialog.review_button)
    assert actions.calls == []
    monkeypatch.setattr(QMessageBox, "information", lambda *_a, **_k: QMessageBox.StandardButton.Ok)
    key(dialog.confirm)
    assert len(actions.calls) == 1
    command, context, granted = actions.calls[0]
    assert command.customer_id == 7 and command.amount == Decimal("20.00")
    assert context.requested_by == "operador" and granted is True


def test_enter_auto_repeat_nao_grava_e_shift_enter_retorna(app):
    service = CustomerService(); actions = Actions(service)
    dialog = CustomerReceiptDialog(service, actions, "operador")
    dialog.show(); dialog.amount.set_value(Decimal("20")); key(dialog.review_button)
    dialog.confirm.setFocus(); app.processEvents()
    key(dialog.confirm, auto=True)
    assert actions.calls == []
    key(dialog.confirm, Qt.KeyboardModifier.ShiftModifier)
    assert dialog.notes.hasFocus()
    assert actions.calls == []


def test_alteracao_apos_revisao_invalida_confirmacao(app):
    service = CustomerService(); actions = Actions(service)
    dialog = CustomerReceiptDialog(service, actions, "operador")
    dialog.show(); app.processEvents()
    dialog.amount.set_value(Decimal("20")); key(dialog.review_button)
    assert dialog.confirm.isVisible() and actions.calls == []
    dialog.amount.set_value(Decimal("19"))
    assert not dialog.confirm.isVisible()
    assert dialog._reviewed_command is None and actions.calls == []


def test_um_enter_avanca_exatamente_um_campo(app):
    service = CustomerService(); dialog = CustomerReceiptDialog(service, Actions(service), "operador")
    dialog.show(); dialog.customer.setFocus(); app.processEvents(); key(dialog.customer)
    assert dialog.amount.hasFocus()
    assert not dialog.method.hasFocus()


def test_cancelar_nao_persiste(app):
    service = CustomerService(); actions = Actions(service)
    dialog = CustomerReceiptDialog(service, actions, "operador")
    dialog.reject()
    assert actions.calls == []


def test_ficha_e_primeiro_campo_destacado_e_pre_preenchido(app):
    dialog = CustomerEditorDialog(CustomerService())
    assert dialog._fields[0] is dialog.record
    assert dialog.record.text() == "5500"
    assert "font-weight:900" in dialog.record.styleSheet()


def test_lista_aplica_cores_legadas_por_faixa_de_saldo(app):
    service = CustomerService()
    dialog = CustomerManagementDialog(service)
    assert dialog.table.item(0, 0).foreground().color().name() == "#ffd33d"


def test_view_model_fichario_recusa_catalogo_e_consumidor_final():
    application = SimpleNamespace(new_session=lambda: SimpleNamespace())
    view_model = FicharioPDVViewModel(application)
    assert view_model.search_products("qualquer") == ()
    with pytest.raises(PermissionError):
        view_model.select_product(1)
    with pytest.raises(ValueError):
        view_model.select_final_consumer()
