from __future__ import annotations

from dataclasses import dataclass

from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.commercial_action_service import CommercialActionService
from commercial.application.commercial_query_service import CommercialQueryService
from commercial.application.customer_application_service import CustomerApplicationService
from commercial.application.financial_action_service import FinancialActionService
from commercial.application.financial_query_service import FinancialQueryService
from commercial.application.product_application_service import ProductApplicationService
from commercial.application.stock_action_service import StockActionService
from commercial.application.ports import (
    BudgetOutputPort, BudgetPort, CommercialEventPort, SaleReceiptOutputPort,
    SuspendedSalePort,
    DailySalesPort,
)

from .cancellation_gateway import NabiCodeSaleCancellationGateway
from .checkout_gateway import NabiCodeCheckoutGateway
from .customer_gateway import NabiCodeCustomerGateway
from .product_gateway import NabiCodeProductGateway
from .read_gateway import NabiCodeCommercialReadGateway
from .customer_account_gateway import NabiCodeCustomerAccountGateway
from .customer_receipt_gateway import NabiCodeCustomerReceiptGateway
from .financial_gateway import NabiCodeFinancialGateway
from .stock_gateway import NabiCodeProductStockGateway


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
    financial_query: FinancialQueryService | None = None
    financial_actions: FinancialActionService | None = None
    product_application: ProductApplicationService | None = None
    stock_actions: StockActionService | None = None
    purchase_service: object | None = None
    product_service: object | None = None
    stock_service: object | None = None

    @classmethod
    def from_existing(
        cls,
        *,
        cliente_repository,
        produto_service,
        pdv_transaction_service,
        pdv_service,
        events: CommercialEventPort | None = None,
        receipt_output: SaleReceiptOutputPort | None = None,
        budgets: BudgetPort | None = None,
        budget_output: BudgetOutputPort | None = None,
        suspended_sales: SuspendedSalePort | None = None,
        daily_sales: DailySalesPort | None = None,
        financeiro_repository=None,
        cobranca_service=None,
        dashboard_repository=None,
        action_events=None,
        financial_events=None,
        customer_registration_service=None,
        database=None,
        financeiro_service=None,
        estoque_service=None,
        stock_events=None,
        purchase_service=None,
    ) -> "CommercialContainer":
        customers = NabiCodeCustomerGateway(cliente_repository)
        products = NabiCodeProductGateway(produto_service)
        checkout = NabiCodeCheckoutGateway(pdv_transaction_service, pdv_service)
        application = PDVApplicationService(
            customers=customers,
            products=products,
            checkout_gateway=checkout,
            events=events,
            receipt_output=receipt_output,
            budgets=budgets,
            budget_output=budget_output,
            suspended_sales=suspended_sales,
            daily_sales=daily_sales,
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
        product_application = None
        stock_actions = None
        if estoque_service is not None:
            stock_gateway = NabiCodeProductStockGateway(produto_service, estoque_service)
            product_application = ProductApplicationService(stock_gateway, stock_gateway)
            stock_actions = StockActionService(stock_gateway, stock_events)
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
                customer_accounts=accounts, product_application=product_application,
            )
        if customer_registration_service is not None and accounts is not None:
            customer_application = CustomerApplicationService(
                registration=customer_registration_service,
                customers=customers,
                accounts=accounts,
            )
        financial_query = None
        financial_actions = None
        if all(item is not None for item in (financeiro_service, financeiro_repository, cobranca_service)):
            financial_gateway = NabiCodeFinancialGateway(
                financeiro_service, financeiro_repository, cobranca_service
            )
            financial_query = FinancialQueryService(financial_gateway)
            financial_actions = FinancialActionService(financial_gateway, financial_events)
        return cls(
            application, customers, products, checkout, query, actions,
            customer_application, financial_query, financial_actions,
            product_application, stock_actions, purchase_service,
            produto_service, estoque_service,
        )
