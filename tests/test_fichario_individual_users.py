import sqlite3
from datetime import timedelta
from types import SimpleNamespace
from decimal import Decimal

import pytest

from fichario.user_service import FicharioSecurityService
from fichario.authenticated_operations import (
    AuthenticatedReceipts, FicharioTransactionService, FicharioFinanceRepository,
)
from commercial.application.action_dto import ActionContext, ActionOrigin
from database import DatabaseManager
from services.pdv_service import PDVService


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "test.db"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE log_acesso_admin(data TEXT,sucesso INT,detalhes TEXT);
        CREATE TABLE auditoria(data TEXT,usuario TEXT,modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
        CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, cliente_id INTEGER,tipo TEXT,descricao TEXT,
            valor REAL,data TEXT,vencimento TEXT,status_pagamento TEXT,valor_aberto REAL,
            forma_pagamento TEXT,responsavel TEXT);
        CREATE TABLE parcelas(id INTEGER PRIMARY KEY,movimentacao_id INT,numero_parcela INT,
            valor_parcela REAL,vencimento TEXT,status TEXT,valor_pago REAL,data_pagamento TEXT,
            atraso_registrado INT,dados_confiaveis INT);
    """)
    connection.commit()
    connection.close()
    security = FicharioSecurityService(lambda: sqlite3.connect(path))
    security.setup_admin("dona", "Proprietária", "teste123")
    security.authenticate("dona", "teste123")
    return path, security


def test_setup_and_login_have_no_automatic_session(setup):
    _, security = setup
    assert not security.needs_setup()
    with pytest.raises(PermissionError):
        security.setup_admin("intruso", "X", "teste123")
    with pytest.raises(PermissionError):
        security.start_session_without_password()
    assert security.authenticate("dona", "errada") is None
    assert security.session is None
    assert security.authenticate("dona", "teste123").user.username == "dona"


def test_user_management_preserves_last_admin_and_requires_permission(setup):
    _, security = setup
    security.save_account("ana", "Ana", "teste123", "OPERADOR")
    with pytest.raises(ValueError):
        security.save_account("dona", "Dona", "", "ADMIN", False, existing=True)
    security.authenticate("ana", "teste123")
    with pytest.raises(PermissionError):
        security.save_account("intruso", "Intruso", "teste123", "ADMIN")


@pytest.mark.parametrize("reason", ["expired", "disabled", "permission"])
def test_receipt_refused_before_delegate_when_session_invalid(setup, reason):
    _, security = setup
    security.save_account("ana", "Ana", "teste123", "GERENTE")
    security.authenticate("ana", "teste123")
    if reason == "expired":
        security.session.last_activity_at -= timedelta(minutes=16)
    else:
        second = FicharioSecurityService(security.connection_factory)
        if reason == "disabled":
            second.set_user_active("ana", False)
        else:
            second.update_user("ana", profile="OPERADOR")
    calls = []
    actions = SimpleNamespace(receive_customer_payment=lambda *a, **k: calls.append(k))
    with pytest.raises(PermissionError):
        AuthenticatedReceipts(actions, security).receive_customer_payment(
            object(), context=ActionContext("forjado", ActionOrigin.UI),
            confirmation_granted=True,
        )
    assert calls == []


def test_receipt_actor_is_session_not_gui(setup):
    _, security = setup
    calls = []
    actions = SimpleNamespace(receive_customer_payment=lambda *a, **k: calls.append(k))
    AuthenticatedReceipts(actions, security).receive_customer_payment(
        object(), context=ActionContext("forjado", ActionOrigin.UI), confirmation_granted=True
    )
    assert calls[0]["context"].requested_by == "dona"


def test_sale_records_actor_and_rolls_back_on_audit_failure(setup):
    path, security = setup
    factory = lambda: sqlite3.connect(path)
    service = FicharioTransactionService(
        factory, security=security, pdv_service=PDVService(factory),
        estoque_service=SimpleNamespace(baixar_itens_venda_na_transacao=lambda *a, **k: None),
        financeiro_service=SimpleNamespace(),
    )
    command = dict(customer_id=1, customer_name="Teste", user="forjado", received=10, change=0,
                   items=[dict(item="Avulso", qtd=1, preco=10, subtotal=10, item_avulso=True)],
                   payments=[dict(forma="DINHEIRO", valor=10)])
    result = service.finalize_sale(**command)
    connection = factory()
    assert connection.execute("SELECT responsavel FROM movimentacoes WHERE id=?", (result.sale_id,)).fetchone()[0] == "dona"
    connection.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON auditoria BEGIN SELECT RAISE(ABORT,'test'); END")
    connection.commit()
    with pytest.raises(sqlite3.DatabaseError):
        service.finalize_sale(**command)
    assert connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0] == 1
    connection.close()


def test_payment_actor_written_in_same_transaction(setup):
    path, security = setup
    repository = FicharioFinanceRepository(DatabaseManager(path), security=security)
    connection = sqlite3.connect(path)
    connection.execute("BEGIN")
    ident = repository.inserir_movimento_pagamento_cliente(
        cliente_id=1, descricao="teste", valor=Decimal("20"), data="31/08/2026",
        forma_pagamento="PIX", connection=connection,
    )
    assert connection.execute("SELECT responsavel FROM movimentacoes WHERE id=?", (ident,)).fetchone()[0] == "dona"
    connection.rollback()
    assert connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0] == 0
    connection.close()


def test_picker_uses_real_id_and_explicit_selection(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from fichario.customer_picker import CustomerPickerDialog
    app = QApplication.instance() or QApplication([])
    customer = SimpleNamespace(customer_id=81, record_number=900, name="Ana",
                               phone="123", debt_balance=Decimal("400"))
    service = SimpleNamespace(list_customers=lambda *a, **k: (customer,),
                              get_customer=lambda ident: customer if ident == 81 else None)
    dialog = CustomerPickerDialog(service)
    assert dialog.selected_customer is None
    assert dialog.table.item(0, 3).text() == "R$ 400,00"
    dialog.choose()
    assert dialog.selected_customer.customer_id == 81
    dialog.close()


def test_users_dialog_creates_account_without_storing_plain_password(setup):
    from PySide6.QtWidgets import QApplication
    from fichario.users_dialog import AccountDialog
    app = QApplication.instance() or QApplication([])
    path, security = setup
    dialog = AccountDialog(security)
    dialog.username.setText("maria")
    dialog.name.setText("Maria")
    dialog.password.setText("segredo123")
    dialog.confirm.setText("segredo123")
    dialog.save()
    assert security.get_user("maria").profile == "OPERADOR"
    connection = sqlite3.connect(path)
    assert "segredo123" not in connection.execute(
        "SELECT valor FROM configuracoes WHERE chave=?", (security.CONFIG_KEY,)
    ).fetchone()[0]
    connection.close()
    dialog.close()


def test_real_fichario_sale_and_payment_keep_authorship(tmp_path):
    from database.schema_initializer import initialize_database
    from commercial.infrastructure.runtime import create_commercial_container
    from commercial.application.customer_dto import CustomerCreateCommand, CustomerReceiptCommand
    from repositories.dashboard_repository import DashboardRepository
    from datetime import date
    db = DatabaseManager(tmp_path / "real-test.db")
    initialize_database(
        db_name=str(db.database_path), backup_dir=str(tmp_path / "backup"),
        pdf_dir=str(tmp_path / "pdf"), schema_version=21,
        last_database_update={"executada": False, "de": 0, "para": 21, "backup": ""},
        network_mode=False, network_role="local", connect=db.connect,
        read_existing_version=lambda: 0, backup_before_update=lambda *a: "",
    )
    security = FicharioSecurityService(db.connect)
    security.setup_admin("ana", "Ana", "teste123")
    security.authenticate("ana", "teste123")
    container = create_commercial_container(
        db, transaction_factory=lambda *a, **k: FicharioTransactionService(*a, security=security, **k),
        finance_repository_factory=lambda database: FicharioFinanceRepository(database, security=security),
    )
    customer = container.customer_application.create_customer(
        CustomerCreateCommand(name="Fictício", code="TEST", credit_limit=Decimal("1000"))
    )
    result = container.checkout.transaction_service.finalize_sale(
        customer_id=customer.customer_id, customer_name=customer.name, user="falso",
        items=[dict(item="Avulso", qtd=1, preco=500, subtotal=500, item_avulso=True)],
        payments=[dict(forma="DINHEIRO", valor=100), dict(forma="CREDIARIO", valor=400)],
        received=500, change=0,
    )
    before = DashboardRepository(db).daily_credit_flow()
    assert before.received_total == 100 and before.financed_total == 400
    security.save_account("bia", "Bia", "teste123", "GERENTE")
    security.authenticate("bia", "teste123")
    receipt = AuthenticatedReceipts(container.actions, security).receive_customer_payment(
        CustomerReceiptCommand(customer.customer_id, Decimal("40"), "PIX", date.today()),
        context=ActionContext("falso", ActionOrigin.UI), confirmation_granted=True,
    )
    assert receipt.committed, receipt.message
    with db.session() as conn:
        assert conn.execute("SELECT responsavel FROM movimentacoes WHERE id=?", (result.sale_id,)).fetchone()[0] == "ana"
        assert conn.execute("SELECT responsavel FROM movimentacoes WHERE id=?", (receipt.resource_id,)).fetchone()[0] == "bia"
    after = DashboardRepository(db).daily_credit_flow()
    assert after.received_total == 140 and after.financed_total == 400
