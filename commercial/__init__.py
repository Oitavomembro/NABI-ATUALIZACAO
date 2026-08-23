"""Núcleo comercial puro do NabiCode.

Este pacote não depende de interface gráfica, persistência ou provedores de IA.
"""

from .application.dto import (
    CheckoutCommand,
    CheckoutReceipt,
    CheckoutResult,
    CustomerRecord,
    ProductRecord,
)
from .application.pdv_application_service import PDVApplicationService
from .application.pdv_session import CheckoutState, PDVSession
from .domain.cart import Cart, CartItem
from .domain.credit import CreditInstallment, CreditTerms
from .domain.money import MoneyCodec, MoneyValueError
from .domain.payments import Payment, PaymentMethod, PaymentPlan, PaymentValidation

__all__ = [
    "Cart",
    "CartItem",
    "CheckoutCommand",
    "CheckoutReceipt",
    "CheckoutResult",
    "CheckoutState",
    "CreditInstallment",
    "CreditTerms",
    "MoneyCodec",
    "MoneyValueError",
    "CustomerRecord",
    "PDVApplicationService",
    "PDVSession",
    "Payment",
    "PaymentMethod",
    "PaymentPlan",
    "PaymentValidation",
    "ProductRecord",
]
