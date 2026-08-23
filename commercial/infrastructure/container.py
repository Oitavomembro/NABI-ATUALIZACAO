from __future__ import annotations

from dataclasses import dataclass

from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.commercial_action_service import CommercialActionService
from commercial.application.commercial_query_service import CommercialQueryService
from commercial.application.customer_application_service import CustomerApplicationService
from commercial.application.ports import CommercialEventPort

from .cancellation_gateway import NabiCodeSaleCancellationGateway
from .checkout_gateway import NabiCodeCheckoutGateway
from .customer_gateway import NabiCodeCustomerGateway
from .product_gateway import NabiCodeProductGateway
from .read_gateway import NabiCodeCommercialReadGateway
from .customer_account_gateway import NabiCodeCustomerAccountGateway
from .customer_receipt_gateway import NabiCodeCustomerReceiptGateway


@dataclass(frozen=True, slots=True)
class CommercialContainer:
    """Composição explícita usando instâncias já configuradas pelo NabiCode."""

    application: PDVApplicationService
    customers: NabiCodeCustomerGateway
    products: NabiCodeProductGateway
    checkout: NabiCodeCheckoutGateway
    query: CommercialQueryService | None = None
    actions: CommercialActionService | None = None
    customer_application: CustomerApplicationService | None = None

    @classmethod
    def from_existing(
        cls,
        *,
        cliente_repository,
        produto_service,
        pdv_transaction_service,
        pdv_service,
        events: CommercialEventPort | None = None,
        financeiro_repository=None,
        cobranca_service=None,
        dashboard_repository=None,
        action_events=None,
        customer_registration_service=None,
        database=None,
        financeiro_service=None,
    ) -> "CommercialContainer":
        customers = NabiCodeCustomerGateway(cliente_repository)
        products = NabiCodeProductGateway(produto_service)
        checkout = NabiCodeCheckoutGateway(pdv_transaction_service, pdv_service)
        application = PDVApplicationService(
            customers=customers,
            products=products,
            checkout_gateway=checkout,
            events=events,
        )
        cancellation = NabiCodeSaleCancellationGateway(pdv_transaction_service)
        accounts = None
        receipt_gateway = None
        customer_application = None
        if database is not None and financeiro_repository is not None:
            accounts = NabiCodeCustomerAccountGateway(
                database=database, financeiro_repository=financeiro_repository
            )
        if financeiro_service is not None:
            receipt_gateway = NabiCodeCustomerReceiptGateway(financeiro_service)
        actions = CommercialActionService(
            pdv=application, cancellation=cancellation, events=action_events,
            customer_receipts=receipt_gateway,
        )
        query = None
        if all(item is not None for item in (
            financeiro_repository, cobranca_service, dashboard_repository
        )):
            reporting = NabiCodeCommercialReadGateway(
                transaction_service=pdv_transaction_service,
                financeiro_repository=financeiro_repository,
                cobranca_service=cobranca_service,
                dashboard_repository=dashboard_repository,
            )
            query = CommercialQueryService(
                customers=customers, products=products, reporting=reporting,
                customer_accounts=accounts,
            )
        if customer_registration_service is not None and accounts is not None:
            customer_application = CustomerApplicationService(
                registration=customer_registration_service,
                customers=customers,
                accounts=accounts,
            )
        return cls(
            application, customers, products, checkout, query, actions,
            customer_application,
        )
