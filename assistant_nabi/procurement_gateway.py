from __future__ import annotations

from .confirmations import ConfirmedDraftAuthorization


class NabiCodeProcurementAssistantGateway:
    def __init__(self, purchase_management_service) -> None:
        if purchase_management_service is None:
            raise ValueError("O serviço oficial de compras é obrigatório.")
        self._service = purchase_management_service

    @staticmethod
    def _grant(draft, authorization, operation):
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("A operação exige autorização emitida pelo broker.")
        return authorization.consume(draft, operation=operation)

    def execute_supplier(self, draft, authorization):
        if getattr(draft, "operation_kind", "") != "SUPPLIER_CREATE":
            raise TypeError("O rascunho não representa cadastro de fornecedor.")
        grant = self._grant(draft, authorization, "SUPPLIER_CREATE")
        return self._service.create_supplier_assisted(
            draft.name, legal_name=draft.legal_name, document=draft.document,
            phone=draft.phone, email=draft.email,
            expected_username=grant.username,
            idempotency_key=f"nabi:supplier:{draft.draft_id}",
            operation_fingerprint=draft.fingerprint,
        )

    def execute_order(self, draft, authorization):
        if getattr(draft, "operation_kind", "") != "PURCHASE_ORDER_CREATE":
            raise TypeError("O rascunho não representa novo pedido de compra.")
        grant = self._grant(draft, authorization, "PURCHASE_ORDER_CREATE")
        return self._service.create_order_assisted(
            draft.supplier_id,
            tuple({
                "produto_id": item.product_id,
                "quantidade": format(item.quantity, "f"),
                "custo_unitario": format(item.unit_cost, "f"),
            } for item in draft.items),
            notes=draft.notes, expected_username=grant.username,
            idempotency_key=f"nabi:purchase-order:{draft.draft_id}",
            operation_fingerprint=draft.fingerprint,
        )
