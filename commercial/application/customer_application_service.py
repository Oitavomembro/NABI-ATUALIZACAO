from __future__ import annotations

from .customer_dto import (
    CustomerCreateCommand, CustomerDetails, CustomerStatement, CustomerUpdateCommand,
)
from .ports import CustomerAccountPort, CustomerLookupPort
from .query_dto import CustomerCreditSummary


class CustomerApplicationService:
    """API de clientes sem GUI e sem conhecimento de banco."""

    def __init__(self, *, registration, customers: CustomerLookupPort, accounts: CustomerAccountPort) -> None:
        self._registration = registration
        self._customers = customers
        self._accounts = accounts

    def create_customer(self, command: CustomerCreateCommand) -> CustomerDetails:
        customer_id = self._registration.criar(
            nome=command.name, codigo=command.code, numero_ficha=command.record_number,
            cpf=command.cpf, rg=command.rg, telefone=command.phone,
            endereco=command.address, observacoes=command.notes, limite=command.credit_limit,
        )
        return self.get_customer(customer_id)

    def next_record_number(self) -> int:
        return self._registration.next_record_number()

    def update_customer(self, command: CustomerUpdateCommand) -> CustomerDetails:
        self._registration.editar(
            command.customer_id, nome=command.name, codigo=command.code,
            numero_ficha=command.record_number, cpf=command.cpf, rg=command.rg,
            telefone=command.phone, endereco=command.address,
            observacoes=command.notes, limite=command.credit_limit,
        )
        return self.get_customer(command.customer_id)

    def get_customer(self, customer_id: int) -> CustomerDetails:
        details = self._accounts.details(customer_id)
        if details is None:
            raise ValueError("Cliente não encontrado.")
        return details

    def search_customers(self, term: str, *, limit: int = 30):
        return self._customers.search(term, limit=limit)

    def list_customers(self, term: str = "", *, limit: int = 250) -> tuple[CustomerDetails, ...]:
        records = self._customers.list(term, limit=limit)
        return tuple(self.get_customer(record.customer_id) for record in records)

    def customer_statement(self, customer_id: int) -> CustomerStatement:
        return self._accounts.statement(customer_id)

    def customer_credit(self, customer_id: int) -> CustomerCreditSummary:
        details = self.get_customer(customer_id)
        return CustomerCreditSummary(
            customer_id=details.customer_id,
            credit_limit=details.credit_limit,
            debt_balance=details.debt_balance,
            available_credit=details.available_credit,
        )
