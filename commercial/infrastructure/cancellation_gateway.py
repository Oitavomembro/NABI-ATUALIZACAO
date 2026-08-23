from __future__ import annotations

from commercial.application.action_dto import PersistedCancellation


class NabiCodeSaleCancellationGateway:
    def __init__(self, transaction_service) -> None:
        self.transaction_service = transaction_service

    def cancel(self, sale_id: int, *, user: str) -> PersistedCancellation:
        normalized_id = int(sale_id)
        self.transaction_service.cancel_sale(normalized_id, user=user)
        return PersistedCancellation(normalized_id)
