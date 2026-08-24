from __future__ import annotations

from .confirmations import ConfirmedDraftAuthorization

class NabiCodePurchaseAssistantGateway:
    """Executa somente recebimento já confirmado pelo serviço oficial."""

    def __init__(self, purchase_service) -> None:
        if purchase_service is None:
            raise ValueError("Serviço oficial de compras obrigatório.")
        self._service = purchase_service
        self._repository = purchase_service.repository

    def get_open_order(self, order_id: int):
        order = self._repository.obter_pedido(int(order_id))
        if order is None or str(order.get("status") or "").upper() in {"RECEBIDO", "CANCELADO"}:
            return None
        return order

    def execute(self, draft, authorization):
        if getattr(draft, "operation_kind", "") != "PURCHASE_RECEIPT":
            raise TypeError("O rascunho não representa recebimento de compra.")
        if self.get_open_order(draft.order_id) is None:
            raise ValueError("O pedido não está mais aberto para recebimento.")
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("O recebimento exige autorização emitida pelo broker.")
        grant = authorization.consume(draft, operation="PURCHASE_RECEIPT")
        return self._service.receber(
            draft.order_id,
            tuple({
                "pedido_item_id": item.order_item_id,
                "quantidade": format(item.quantity, "f"),
                "custo_unitario": format(item.unit_cost, "f"),
            } for item in draft.items),
            documento=draft.document,
            observacao="Recebimento confirmado pela Nabi",
            usuario=grant.username,
            gerar_conta_pagar=draft.generate_payable,
            data_vencimento=draft.due_date,
            idempotency_key=f"nabi:purchase:{draft.draft_id}",
            operation_fingerprint=draft.fingerprint,
        )
