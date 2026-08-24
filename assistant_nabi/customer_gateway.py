from __future__ import annotations

from commercial.application.customer_dto import CustomerCreateCommand

from .confirmations import ConfirmedDraftAuthorization


class NabiCodeCustomerRegistrationGateway:
    """Executa somente cadastro confirmado pelo serviço Commercial oficial."""

    def __init__(self, customer_service) -> None:
        if customer_service is None:
            raise ValueError("O serviço oficial de clientes é obrigatório.")
        self._service = customer_service

    def execute(self, draft, authorization):
        if getattr(draft, "operation_kind", "") != "CUSTOMER_CREATE":
            raise TypeError("O rascunho não representa cadastro de cliente.")
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("O cadastro exige autorização emitida pelo broker.")
        grant = authorization.consume(draft, operation="CUSTOMER_CREATE")
        return self._service.create_customer_assisted(
            CustomerCreateCommand(
                name=draft.name, code=draft.code,
                record_number=draft.record_number, cpf=draft.cpf, rg=draft.rg,
                phone=draft.phone, address=draft.address, notes=draft.notes,
                credit_limit=draft.credit_limit,
            ),
            username=grant.username,
            idempotency_key=f"nabi:customer:{draft.draft_id}",
            operation_fingerprint=draft.fingerprint,
        )
