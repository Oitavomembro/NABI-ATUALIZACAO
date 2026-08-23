from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from commercial.application.customer_dto import CustomerDetails
from fichario.receipt_dialog import CustomerReceiptDialog


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
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.No)
    key(dialog.confirm)
    assert actions.calls == []
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *_a, **_k: QMessageBox.StandardButton.Ok)
    key(dialog.confirm)
    assert len(actions.calls) == 1
    command, context, granted = actions.calls[0]
    assert command.customer_id == 7 and command.amount == Decimal("20.00")
    assert context.requested_by == "operador" and granted is True


def test_enter_auto_repeat_nao_grava_e_shift_enter_retorna(app):
    service = CustomerService(); actions = Actions(service)
    dialog = CustomerReceiptDialog(service, actions, "operador")
    dialog.show(); dialog.confirm.setFocus(); app.processEvents()
    key(dialog.confirm, auto=True)
    assert actions.calls == []
    key(dialog.confirm, Qt.KeyboardModifier.ShiftModifier)
    assert dialog.notes.hasFocus()
    assert actions.calls == []


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
