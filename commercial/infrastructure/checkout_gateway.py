from __future__ import annotations

from commercial.application.dto import CheckoutCommand, CustomerRecord
from commercial.application.ports import PersistedCheckout
from commercial.domain.payments import PaymentMethod


class NabiCodeCheckoutGateway:
    """Traduz contratos puros para PDVTransactionService sem mover seu SQL."""

    def __init__(self, transaction_service, pdv_service) -> None:
        self.transaction_service = transaction_service
        self.pdv_service = pdv_service

    def checkout(
        self,
        command: CheckoutCommand,
        *,
        customer: CustomerRecord,
        user: str,
    ) -> PersistedCheckout:
        items = [
            {
                "produto_id": item.product_id,
                "item": item.description,
                "qtd": item.quantity,
                "preco": item.net_unit_price,
                "subtotal": item.subtotal,
                "item_avulso": item.is_loose,
            }
            for item in command.items
        ]
        if command.items_total != command.final_total:
            items = self.pdv_service.ratear_total_itens(items, command.final_total)

        payments = [
            {"forma": payment.method.value, "valor": payment.amount}
            for payment in command.payment_plan.payments
        ]
        if command.credit_terms is not None:
            credit_payment = next(
                payment
                for payment in payments
                if payment["forma"] == PaymentMethod.STORE_CREDIT.value
            )
            credit_payment["parcelas"] = command.credit_terms.installment_count
            credit_payment["primeiro_vencimento"] = (
                command.credit_terms.installments[0].due_date.isoformat()
            )

        validation = command.payment_plan.validate_against(command.final_total)
        finalized = self.transaction_service.finalize_sale(
            customer_id=command.customer_id,
            customer_name=customer.name,
            items=items,
            payments=payments,
            received=validation.received,
            change=validation.change,
            user=user,
        )
        return PersistedCheckout(
            sale_id=int(finalized.sale_id),
            total=finalized.total,
            received=validation.received,
            change=finalized.change,
            payment_description=finalized.payment_description,
            status=finalized.status,
        )
