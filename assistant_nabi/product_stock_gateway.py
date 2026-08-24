from __future__ import annotations

from commercial.application.product_dto import ProductCreateCommand, StockAdjustmentCommand, StockMovementCommand
from .confirmations import ConfirmedDraftAuthorization


class NabiCodeProductStockAssistantGateway:
    """Executa somente rascunhos confirmados pela fachada autorizada."""

    def __init__(self, management_service):
        if management_service is None:
            raise ValueError("A fachada oficial de produtos é obrigatória.")
        self._management = management_service

    def execute(self, draft, authorization):
        operation = str(getattr(draft, "operation_kind", ""))
        if operation not in {"PRODUCT_CREATE", "STOCK_RECEIVE", "STOCK_REMOVE", "STOCK_ADJUST"}:
            raise TypeError("O rascunho não representa produto/estoque assistido.")
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("A operação exige autorização emitida pelo broker.")
        grant = authorization.consume(draft, operation=operation)
        key = f"nabi:product-stock:{draft.draft_id}"
        if operation == "PRODUCT_CREATE":
            command = ProductCreateCommand(
                draft.code, draft.description, draft.sale_price, "MERCADORIA",
                draft.barcode, draft.cost_price, draft.current_stock,
                draft.minimum_stock, False, draft.category_id,
            )
        elif operation == "STOCK_ADJUST":
            command = StockAdjustmentCommand(draft.product_id, draft.new_balance, draft.reason)
        else:
            command = StockMovementCommand(draft.product_id, draft.amount, draft.reason, draft.reference)
        return self._management.execute_assisted(
            operation, command, username=grant.username,
            idempotency_key=key, operation_fingerprint=draft.fingerprint,
        )
