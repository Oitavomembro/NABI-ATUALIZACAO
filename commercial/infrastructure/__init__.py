"""Adaptadores do domínio comercial para o backend atual do NabiCode."""

from .checkout_gateway import NabiCodeCheckoutGateway
from .container import CommercialContainer
from .customer_gateway import NabiCodeCustomerGateway
from .product_gateway import NabiCodeProductGateway
from .cancellation_gateway import NabiCodeSaleCancellationGateway
from .read_gateway import NabiCodeCommercialReadGateway
from .customer_account_gateway import NabiCodeCustomerAccountGateway
from .customer_receipt_gateway import NabiCodeCustomerReceiptGateway
from .financial_gateway import NabiCodeFinancialGateway
from .stock_gateway import NabiCodeProductStockGateway

__all__ = [
    "CommercialContainer",
    "NabiCodeCheckoutGateway",
    "NabiCodeCustomerGateway",
    "NabiCodeProductGateway",
    "NabiCodeSaleCancellationGateway",
    "NabiCodeCommercialReadGateway",
    "NabiCodeCustomerAccountGateway",
    "NabiCodeCustomerReceiptGateway",
    "NabiCodeFinancialGateway",
    "NabiCodeProductStockGateway",
]
