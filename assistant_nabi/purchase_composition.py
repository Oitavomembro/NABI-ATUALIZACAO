from __future__ import annotations

from .purchase_drafts import PurchaseReceiptDraftService
from .purchase_gateway import NabiCodePurchaseAssistantGateway


def create_purchase_assistant_components(commercial_container):
    """Compõe preparação e execução sobre a mesma autoridade de compras."""
    purchase = getattr(commercial_container, "purchase_service", None)
    if purchase is None:
        raise RuntimeError("Serviço oficial de compras não está configurado.")
    gateway = NabiCodePurchaseAssistantGateway(purchase)
    return PurchaseReceiptDraftService(gateway), gateway
