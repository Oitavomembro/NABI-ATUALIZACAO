from __future__ import annotations

from .customer_dto import (
    CustomerCreateCommand, CustomerDetails, CustomerPurchaseBehavior,
    CustomerStatement, CustomerUpdateCommand,
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
            email=command.email, inscricao_estadual=command.state_registration,
            contribuinte_icms=command.icms_taxpayer,
            fiscal_logradouro=command.fiscal_street, fiscal_numero=command.fiscal_number,
            fiscal_bairro=command.fiscal_district,
            fiscal_codigo_municipio=command.fiscal_city_code,
            fiscal_municipio=command.fiscal_city, fiscal_uf=command.fiscal_state,
            fiscal_cep=command.fiscal_zip_code,
        )
        return self.get_customer(customer_id)

    def create_customer_assisted(
        self, command: CustomerCreateCommand, *, username: str,
        idempotency_key: str, operation_fingerprint: str,
    ) -> CustomerDetails:
        create = getattr(self._registration, "criar_assistido", None)
        if not callable(create):
            raise RuntimeError("Cadastro assistido idempotente não está disponível.")
        customer_id = create(
            nome=command.name, codigo=command.code,
            numero_ficha=command.record_number, cpf=command.cpf, rg=command.rg,
            telefone=command.phone, endereco=command.address,
            observacoes=command.notes, limite=command.credit_limit,
            usuario=username, idempotency_key=idempotency_key,
            operation_fingerprint=operation_fingerprint,
        )
        return self.get_customer(customer_id)

    def next_record_number(self) -> int:
        return self._registration.next_record_number()

    def fiscal_address_defaults(self) -> dict[str, str]:
        provider = getattr(self._registration, "fiscal_address_defaults", None)
        return dict(provider() if callable(provider) else {})

    def update_customer(self, command: CustomerUpdateCommand) -> CustomerDetails:
        self._registration.editar(
            command.customer_id, nome=command.name, codigo=command.code,
            numero_ficha=command.record_number, cpf=command.cpf, rg=command.rg,
            telefone=command.phone, endereco=command.address,
            observacoes=command.notes, limite=command.credit_limit,
            email=command.email, inscricao_estadual=command.state_registration,
            contribuinte_icms=command.icms_taxpayer,
            fiscal_logradouro=command.fiscal_street, fiscal_numero=command.fiscal_number,
            fiscal_bairro=command.fiscal_district,
            fiscal_codigo_municipio=command.fiscal_city_code,
            fiscal_municipio=command.fiscal_city, fiscal_uf=command.fiscal_state,
            fiscal_cep=command.fiscal_zip_code,
        )
        return self.get_customer(command.customer_id)

    def delete_unused_customer(self, customer_id: int) -> None:
        delete = getattr(self._registration, "excluir_cadastro_sem_movimento", None)
        if not callable(delete):
            raise RuntimeError("Exclusão segura de cadastro não está disponível.")
        delete(int(customer_id))

    def get_customer(self, customer_id: int) -> CustomerDetails:
        details = self._accounts.details(customer_id)
        if details is None:
            raise ValueError("Cliente não encontrado.")
        return details

    def search_customers(self, term: str, *, limit: int = 30):
        return self._customers.search(term, limit=limit)

    def list_customers(self, term: str = "", *, limit: int = 250) -> tuple[CustomerDetails, ...]:
        records = self._customers.list(term, limit=limit)
        bulk = getattr(self._accounts, "details_many", None)
        if callable(bulk):
            return tuple(bulk(tuple(record.customer_id for record in records)))
        return tuple(self.get_customer(record.customer_id) for record in records)

    def list_customers_by_ids(self, customer_ids) -> tuple[CustomerDetails, ...]:
        ids = tuple(dict.fromkeys(int(value) for value in customer_ids if int(value) > 0))
        bulk = getattr(self._accounts, "details_many", None)
        if callable(bulk):
            return tuple(bulk(ids))
        return tuple(self.get_customer(customer_id) for customer_id in ids)

    def customer_purchase_behavior(
        self, customer_ids,
    ) -> tuple[CustomerPurchaseBehavior, ...]:
        ids = tuple(dict.fromkeys(int(value) for value in customer_ids if int(value) > 0))
        if not ids:
            return ()
        bulk = getattr(self._accounts, "purchase_behavior_many", None)
        if not callable(bulk):
            return tuple(CustomerPurchaseBehavior(customer_id, 0, 0, 0) for customer_id in ids)
        return tuple(bulk(ids))

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
