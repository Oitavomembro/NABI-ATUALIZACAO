from __future__ import annotations


class NabiCodePurchaseAssistantGateway:
    """Leitura de compras; mutação permanece deliberadamente não exposta à IA."""

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

    def receive(self, *args, **kwargs):
        raise PermissionError(
            "Recebimento assistido bloqueado até existir idempotência persistente no backend."
        )
