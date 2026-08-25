from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.customer_application_service import CustomerApplicationService
from commercial.application.customer_dto import CustomerCreateCommand, CustomerUpdateCommand
from commercial.application.financial_action_service import FinancialActionService
from commercial.application.financial_dto import (
    CreateFinancialTitleCommand,
    SettleFinancialTitleCommand,
)


class SwitchingAuthorizer:
    def __init__(self, actor="operador"):
        self.actor = actor
        self.allowed = True
        self.calls = []

    def __call__(self, module, action):
        self.calls.append((module, action))
        if not self.allowed:
            raise PermissionError("Sessão ou permissão revogada.")
        return self.actor


class RegistrationSpy:
    def __init__(self):
        self.calls = []

    def criar(self, **values):
        self.calls.append(("create", values))
        return 11

    def editar(self, customer_id, **values):
        self.calls.append(("edit", customer_id, values))

    def excluir_cadastro_sem_movimento(self, customer_id):
        self.calls.append(("delete", customer_id))


class AccountsStub:
    @staticmethod
    def details(customer_id):
        return SimpleNamespace(customer_id=customer_id)


class CustomersStub:
    pass


class FinancialGatewaySpy:
    def __init__(self):
        self.calls = []

    @staticmethod
    def _result(title_id=7, payment_id=None):
        return SimpleNamespace(
            title_id=title_id, payment_id=payment_id, status="ABERTO",
            open_amount=Decimal("10.00"), idempotent_replay=False,
        )

    def create_title(self, kind, command, **values):
        self.calls.append(("create", kind, values))
        return self._result()

    def settle(self, kind, command, **values):
        self.calls.append(("settle", kind, values))
        return self._result(command.title_id, 5)

    def cancel(self, title_id, **values):
        self.calls.append(("cancel", title_id, values))
        return self._result(title_id)

    def reverse_payment(self, payment_id, **values):
        self.calls.append(("reverse", payment_id, values))
        return self._result(payment_id, payment_id)


def _customer_service(authorizer):
    registration = RegistrationSpy()
    service = CustomerApplicationService(
        registration=registration, customers=CustomersStub(), accounts=AccountsStub(),
        mutation_authorizer=authorizer,
    )
    return service, registration


def test_clientes_revalidam_cada_mutacao_e_recusam_janela_com_permissao_retirada():
    authorizer = SwitchingAuthorizer()
    service, registration = _customer_service(authorizer)
    created = service.create_customer(CustomerCreateCommand(name="CLIENTE"))
    assert created.customer_id == 11
    assert registration.calls[0][1]["usuario"] == "operador"
    authorizer.allowed = False
    with pytest.raises(PermissionError, match="revogada"):
        service.update_customer(CustomerUpdateCommand(customer_id=11, name="NOVO"))
    with pytest.raises(PermissionError, match="revogada"):
        service.delete_unused_customer(11)
    assert [call[0] for call in registration.calls] == ["create"]
    assert authorizer.calls == [
        ("clientes", "create"), ("clientes", "edit"), ("clientes", "edit")
    ]


def test_financeiro_troca_contexto_stale_pelo_ator_corrente_em_cada_acao():
    authorizer = SwitchingAuthorizer("ana")
    gateway = FinancialGatewaySpy()
    service = FinancialActionService(gateway, mutation_authorizer=authorizer)
    stale = ActionContext("usuario-da-janela", ActionOrigin.UI)
    command = CreateFinancialTitleCommand(Decimal("10"), date.today())
    first = service.create_receivable(command, context=stale, confirmed=True)
    authorizer.actor = "bruno"
    second = service.create_payable(command, context=stale, confirmed=True)
    assert first.context.requested_by == "ana"
    assert second.context.requested_by == "bruno"
    assert [call[2]["user"] for call in gateway.calls] == ["ana", "bruno"]
    assert authorizer.calls == [("financeiro", "create"), ("financeiro", "create")]


def test_financeiro_recusado_nao_muta_nem_publica_evento_falso():
    authorizer = SwitchingAuthorizer(); authorizer.allowed = False
    gateway = FinancialGatewaySpy()
    events = SimpleNamespace(calls=[], financial_event=lambda event: events.calls.append(event))
    service = FinancialActionService(gateway, events, authorizer)
    context = ActionContext("stale", ActionOrigin.UI)
    result = service.settle_receivable(
        SettleFinancialTitleCommand(7, Decimal("10"), "PIX", date.today()),
        context=context, confirmed=True,
    )
    assert not result.executed and not result.committed
    assert gateway.calls == []
    assert events.calls == []


def test_financeiro_sem_confirmacao_nao_consulta_autorizacao_nem_muta():
    authorizer = SwitchingAuthorizer()
    gateway = FinancialGatewaySpy()
    service = FinancialActionService(gateway, mutation_authorizer=authorizer)
    result = service.create_receivable(
        CreateFinancialTitleCommand(Decimal("10"), date.today()),
        context=ActionContext("stale", ActionOrigin.UI), confirmed=False,
    )
    assert not result.executed
    assert authorizer.calls == []
    assert gateway.calls == []
