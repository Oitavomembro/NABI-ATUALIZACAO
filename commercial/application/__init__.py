"""API e contratos da camada de aplicação comercial."""

from .dto import (
    CheckoutCommand,
    CheckoutReceipt,
    CheckoutResult,
    CustomerRecord,
    ProductRecord,
)
from .pdv_application_service import PDVApplicationService
from .pdv_session import CheckoutState, PDVSession
from .commercial_query_service import CommercialQueryService
from .commercial_action_service import CommercialActionService
from .action_dto import (
    ActionContext, ActionOrigin, ActionSensitivity, CommercialActionResult,
    PersistedCancellation, SaleCancelled,
)
from .customer_application_service import CustomerApplicationService
from .customer_dto import (
    CustomerCreateCommand, CustomerDetails, CustomerInstallment,
    CustomerPaymentReceived, CustomerReceiptCommand, CustomerReceiptSummary,
    CustomerStatement, CustomerStatementEntry, CustomerUpdateCommand,
    PersistedCustomerReceipt,
)

__all__ = [
    "CheckoutCommand",
    "CheckoutReceipt",
    "CheckoutResult",
    "CheckoutState",
    "CommercialActionResult",
    "CommercialActionService",
    "CommercialQueryService",
    "ActionContext",
    "ActionOrigin",
    "ActionSensitivity",
    "CustomerRecord",
    "CustomerApplicationService",
    "CustomerCreateCommand",
    "CustomerDetails",
    "CustomerInstallment",
    "CustomerPaymentReceived",
    "CustomerReceiptCommand",
    "CustomerReceiptSummary",
    "CustomerStatement",
    "CustomerStatementEntry",
    "CustomerUpdateCommand",
    "PDVApplicationService",
    "PDVSession",
    "ProductRecord",
    "PersistedCancellation",
    "PersistedCustomerReceipt",
    "SaleCancelled",
]
