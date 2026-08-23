from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog

from commercial.application.customer_dto import (
    CustomerDetails, CustomerPurchaseBehavior, CustomerStatement,
)
from ui_qt.commercial.customer_dialog import CustomerEditorDialog, CustomerManagementDialog


def customer(customer_id=7, name="MARIA"):
    return CustomerDetails(
        customer_id, "CLI7", 5507, name, "", "", "71999990000", "RUA A", "",
        Decimal("500"), Decimal("125"), Decimal("375"),
    )


class Service:
    def __init__(self):
        self.rows = [customer()]
        self.calls = []

    def list_customers(self, term="", limit=250):
        self.calls.append(("list", term, limit)); return tuple(self.rows)

    def get_customer(self, customer_id):
        self.calls.append(("get", customer_id)); return self.rows[0]

    def customer_purchase_behavior(self, customer_ids):
        return tuple(
            CustomerPurchaseBehavior(customer_id, 3, 2, 4)
            for customer_id in customer_ids
        )

    def customer_statement(self, customer_id):
        self.calls.append(("statement", customer_id))
        return CustomerStatement(self.rows[0], (), (), (), Decimal("125"), Decimal("0"))

    def create_customer(self, command):
        self.calls.append(("create", command)); return customer(8, command.name)

    def update_customer(self, command):
        self.calls.append(("update", command)); return customer(command.customer_id, command.name)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def key(widget, key, modifiers=Qt.KeyboardModifier.NoModifier, auto=False):
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers, "", auto, 1)
    QApplication.sendEvent(widget, event)


def test_lista_transporta_id_real_e_exibe_saldos(app):
    service = Service(); dialog = CustomerManagementDialog(service)
    assert dialog.table.rowCount() == 1
    assert dialog.selected_customer_id() == 7
    assert [dialog.table.horizontalHeaderItem(index).text() for index in range(6)] == [
        "Ficha", "Nome", "Saldo\ndevedor", "Compras\nsem atraso",
        "Compras\ncom atraso", "Parcelas\natrasadas",
    ]
    assert "nenhuma parcela atrasou" in dialog.table.horizontalHeaderItem(3).toolTip()
    assert "vencidas em aberto" in dialog.table.horizontalHeaderItem(5).toolTip()
    assert dialog.table.item(0, 2).text() == "R$ 125,00"
    assert dialog.table.item(0, 3).text() == "3"
    assert dialog.table.item(0, 4).text() == "2"
    assert dialog.table.item(0, 5).text() == "4"
    assert "RUA A" in dialog.table.item(0, 1).toolTip()
    assert "Endereço: RUA A" in dialog.selected_details.text()
    assert "CPF:" not in dialog.selected_details.text()
    assert "Telefone: 71999990000" in dialog.selected_details.text()
    assert dialog.width() >= 1180 and dialog.height() >= 720
    dialog.close()


def test_enter_busca_uma_acao_shift_enter_retorna_e_auto_repeat_nao_age(app, monkeypatch):
    service = Service(); dialog = CustomerManagementDialog(service)
    dialog.show(); app.processEvents()
    initial = len(service.calls)
    dialog.search.setText("maria")
    key(dialog.search, Qt.Key.Key_Return, auto=True)
    assert len(service.calls) == initial
    key(dialog.search, Qt.Key.Key_Return)
    assert service.calls[-1] == ("list", "maria", 200)
    assert dialog.table.hasFocus()
    monkeypatch.setattr(dialog, "open_statement", lambda *_: service.calls.append(("opened",)))
    key(dialog.table, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert dialog.search.hasFocus()
    assert ("opened",) not in service.calls
    dialog.close()


def test_enter_na_tabela_abre_ficha_uma_vez_com_id_real(app, monkeypatch):
    service = Service(); dialog = CustomerManagementDialog(service)
    executions = []
    monkeypatch.setattr(
        "ui_qt.commercial.customer_dialog.CustomerStatementDialog.exec",
        lambda _self: executions.append("exec") or QDialog.DialogCode.Rejected,
    )
    dialog.table.setFocus(); key(dialog.table, Qt.Key.Key_Return)
    assert service.calls[-1] == ("statement", 7)
    assert executions == ["exec"]
    dialog.close()


def test_filtro_do_card_usa_provedor_limitado_ao_segmento(app):
    service = Service(); calls = []

    def provider(term, limit):
        calls.append((term, limit))
        return (customer(name="CLIENTE DO GRUPO"),)

    dialog = CustomerManagementDialog(
        service, customer_provider=provider, filter_title="CLIENTES DEVENDO",
    )
    assert calls == [("", 60)]
    assert service.calls == []
    assert dialog.table.item(0, 1).text() == "CLIENTE DO GRUPO"
    dialog.search.setText("maria")
    dialog.reload()
    assert calls[-1] == ("maria", 200)
    dialog.close()


def test_dados_ausentes_sao_omitidos_sem_deixar_espaco_vazio(app):
    service = Service()
    base = customer()
    service.rows = [CustomerDetails(
        base.customer_id, base.code, base.record_number, base.name,
        "123.456.789-00", base.rg, "", base.address, base.notes,
        base.credit_limit, base.debt_balance, base.available_credit,
    )]
    dialog = CustomerManagementDialog(service)
    details = dialog.selected_details.text()
    assert "Endereço: RUA A" in details
    assert "CPF: 123.456.789-00" in details
    assert "Telefone:" not in details
    assert "  •     •  " not in details
    dialog.close()


def test_editor_enter_avanca_shift_volta_e_salva_sem_sql(app):
    service = Service(); dialog = CustomerEditorDialog(service)
    dialog.show(); app.processEvents()
    dialog.name.setText("JOAO")
    dialog.record.setFocus(); key(dialog.record, Qt.Key.Key_Return)
    assert dialog.code.hasFocus()
    key(dialog.code, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert dialog.record.hasFocus()
    dialog.save_button.setFocus(); key(dialog.save_button, Qt.Key.Key_Return)
    assert service.calls[-1][0] == "create"
    assert service.calls[-1][1].name == "JOAO"
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_gui_nao_importa_banco_repositorio_ou_fiscal():
    source = (__import__("pathlib").Path(__file__).parents[1] / "ui_qt/commercial/customer_dialog.py").read_text()
    for forbidden in ("sqlite3", "database", "repositories", "fiscal", "sefaz"):
        assert forbidden not in source.lower()
