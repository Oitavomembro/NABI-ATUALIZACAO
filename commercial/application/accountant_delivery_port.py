from __future__ import annotations

from typing import Protocol

from .accountant_delivery_dto import AccountantDeliveryPlan, AccountantDeliveryStatus


class AccountantDeliveryGateway(Protocol):
    """Porta explícita da aplicação para uma outbox contábil."""

    def prepare(self, plan: AccountantDeliveryPlan) -> AccountantDeliveryStatus: ...
    def enqueue(self, plan: AccountantDeliveryPlan) -> AccountantDeliveryStatus: ...
    def dispatch(self, plan: AccountantDeliveryPlan) -> AccountantDeliveryStatus: ...
    def check_receipt(self, plan: AccountantDeliveryPlan) -> AccountantDeliveryStatus: ...
