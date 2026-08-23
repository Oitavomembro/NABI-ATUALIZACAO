from __future__ import annotations

from commercial.application.customer_dto import CustomerReceiptCommand, PersistedCustomerReceipt


class NabiCodeCustomerReceiptGateway:
    def __init__(self, financeiro_service) -> None:
        self.financeiro_service = financeiro_service

    def receive(self, command: CustomerReceiptCommand, *, user: str) -> PersistedCustomerReceipt:
        result = self.financeiro_service.receber_pagamento_cliente(
            cliente_id=command.customer_id, valor=command.amount, alvo=None,
            forma_pagamento=command.payment_method, observacao=command.notes,
            usuario=user, data_pagamento=command.payment_date,
        )
        return PersistedCustomerReceipt(
            movement_id=int(result["pagamento_mov_id"]), customer_id=command.customer_id,
            amount=result["valor"], previous_balance=result["saldo_anterior"],
            new_balance=result["novo_saldo"], payment_method=result["forma_pagamento"],
        )
