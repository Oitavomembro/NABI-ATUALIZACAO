from dataclasses import replace
from datetime import datetime
from services.pdv_transaction_service import PDVTransactionService
from repositories.financeiro_repository import FinanceiroRepository


class FicharioFinanceRepository(FinanceiroRepository):
    def __init__(self, database, *, security):
        super().__init__(database)
        self.security = security

    def inserir_movimento_pagamento_cliente(self, *, connection, **kwargs):
        actor = self.security.actor("financeiro", "pay")
        movement_id = super().inserir_movimento_pagamento_cliente(connection=connection, **kwargs)
        connection.execute(
            "UPDATE movimentacoes SET responsavel=? WHERE id=?", (actor, movement_id)
        )
        self.registrar_auditoria(
            usuario=actor, acao="RECEBIMENTO_FICHARIO", objeto=str(movement_id),
            connection=connection,
        )
        return movement_id


class FicharioTransactionService(PDVTransactionService):
    def __init__(self, *args, security, **kwargs):
        super().__init__(*args, **kwargs)
        self.security = security

    def finalize_sale(self, **kwargs):
        actor = self.security.actor("vendas", "create")
        kwargs["user"] = actor
        previous = kwargs.get("after_sale_in_transaction")

        def record(connection, sale_id):
            if self.security.actor("vendas", "create") != actor:
                raise PermissionError("A sessão mudou durante a venda.")
            connection.execute(
                "UPDATE movimentacoes SET responsavel=? WHERE id=?", (actor, sale_id)
            )
            connection.execute(
                "INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado) "
                "VALUES(?,?,?,?,?,?,?)",
                (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), actor,
                 "VENDAS", "VENDA_FICHARIO", str(sale_id), "Autoria da sessão", "SUCESSO"),
            )
            if previous:
                previous(connection, sale_id)

        kwargs["after_sale_in_transaction"] = record
        return super().finalize_sale(**kwargs)

    def cancel_sale(self, sale_id, *, user, **kwargs):
        return super().cancel_sale(
            sale_id, user=self.security.actor("vendas", "cancel"), **kwargs
        )


class AuthenticatedReceipts:
    def __init__(self, actions, security):
        self.actions, self.security = actions, security

    def receive_customer_payment(self, command, *, context, confirmation_granted):
        actor = self.security.actor("financeiro", "pay")
        return self.actions.receive_customer_payment(
            command, context=replace(context, requested_by=actor),
            confirmation_granted=confirmation_granted,
        )


class AuthenticatedCustomers:
    def __init__(self, service, security):
        self.service, self.security = service, security

    def __getattr__(self, name):
        method = getattr(self.service, name)
        actions = {"create_customer": "create", "update_customer": "edit",
                   "delete_unused_customer": "edit"}
        def call(*args, **kwargs):
            self.security.actor("clientes", actions.get(name, "view"))
            return method(*args, **kwargs)
        return call
