from __future__ import annotations

from commercial.application.dto import CheckoutCommand, CustomerRecord
from commercial.application.ports import PersistedCheckout
from commercial.domain.payments import PaymentMethod


class NabiCodeCheckoutGateway:
    """Traduz contratos puros para PDVTransactionService sem mover seu SQL."""

    def __init__(self, transaction_service, pdv_service) -> None:
        self.transaction_service = transaction_service
        self.pdv_service = pdv_service
        self.fiscal_sale_service = None
        self.fiscal_required = False
        self.last_fiscal_submission: dict[str, object] | None = None

    def bind_fiscal(self, fiscal_sale_service, *, required: bool) -> None:
        """Liga o checkout ao fiscal sem permitir queda silenciosa para comercial."""

        self.fiscal_sale_service = fiscal_sale_service
        self.fiscal_required = bool(required)

    def recover_fiscal_sale(self, sale_id: int) -> str:
        """Agenda a única recuperação segura para o estado fiscal atual."""

        if self.fiscal_sale_service is None:
            raise RuntimeError("O serviço fiscal não está conectado ao PDV.")
        document = next(
            (
                row for row in self.fiscal_sale_service.list_sales()
                if int(row.get("sale_id") or 0) == int(sale_id)
            ),
            None,
        )
        if document is None:
            raise ValueError("A venda selecionada não possui vínculo fiscal.")
        status = str(document.get("status") or "").upper()
        queue_id = str(document.get("queue_id") or "").strip()
        if status == "RESPOSTA_DESCONHECIDA":
            if not queue_id:
                raise ValueError("A resposta é desconhecida, mas a fila fiscal não foi localizada.")
            self.fiscal_sale_service.fiscal_service.reconcile_unknown(queue_id)
            return "Consulta oficial agendada. A autorização não será retransmitida."
        if status in {"FALHA", "ERRO"}:
            if not queue_id:
                self.fiscal_sale_service.enqueue_pending(sale_id=int(sale_id))
            else:
                self.fiscal_sale_service.fiscal_service.retry_transmission(queue_id)
            return "Reenvio fiscal agendado com a mesma venda e numeração."
        if status in {"PENDENTE", "ENFILEIRADO", "PROCESSANDO"}:
            return "O documento já está na fila fiscal; o processamento foi solicitado."
        if status == "AUTORIZADO":
            raise ValueError("A NF-e já está autorizada e não deve ser reenviada.")
        if status in {"CANCELADO", "CANCELADO_LOCAL", "CANCELADO_FISCAL"}:
            raise ValueError("Documento cancelado não pode ser reenviado.")
        raise ValueError(f"O estado fiscal {status or 'SEM STATUS'} não permite reenvio.")

    def cancel_fiscal_sale(
        self, sale_id: int, *, password: str, justification: str, user: str
    ) -> None:
        """Cancela na SEFAZ antes de reverter estoque, Caixa e financeiro."""

        if self.fiscal_sale_service is None:
            raise RuntimeError("O serviço fiscal não está conectado ao PDV.")
        self.fiscal_sale_service.cancel_authorized(
            sale_id=int(sale_id), password=str(password),
            justification=str(justification or "").strip(),
        )
        self.transaction_service.cancel_sale(
            int(sale_id), user=str(user or "Sistema"),
            before_cancel_commit=self.fiscal_sale_service.prepare_local_cancellation,
        )
        self.fiscal_sale_service.finalize_local_cancellation(sale_id=int(sale_id))

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

        payments = []
        for payment in command.payment_plan.payments:
            entry = {"forma": payment.method.value, "valor": payment.amount}
            if payment.method in {PaymentMethod.DEBIT, PaymentMethod.CREDIT_CARD}:
                entry.update({
                    "card_integration": 2,
                    "card_authorization": payment.card_authorization,
                })
            payments.append(entry)
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
        draft = None
        self.last_fiscal_submission = None
        if self.fiscal_required:
            if self.fiscal_sale_service is None:
                raise RuntimeError("Modo fiscal ativo, mas o emissor NF-e não foi conectado ao PDV.")
            if any(item["item_avulso"] for item in items):
                raise ValueError("Venda fiscal exige que todos os itens estejam cadastrados.")
            config = self.fiscal_sale_service.fiscal_service.load_config()
            if not bool(config.get("enabled")):
                raise ValueError("O modo fiscal está ativo, mas a configuração fiscal não está habilitada.")
            if str(config.get("default_model") or "") != "55":
                raise ValueError("Esta empresa exige NF-e modelo 55 como modelo fiscal padrão.")
            recipient, destination = self.fiscal_sale_service.recipient_for_customer(
                command.customer_id, model="55"
            )
            draft = self.fiscal_sale_service.prepare(
                items=items,
                payments=payments,
                recipient=recipient,
                destination=destination,
            )
        try:
            finalized = self.transaction_service.finalize_sale(
                customer_id=command.customer_id,
                customer_name=customer.name,
                items=items,
                payments=payments,
                received=validation.received,
                change=validation.change,
                user=user,
                after_sale_in_transaction=(
                    (lambda connection, sale_id: self.fiscal_sale_service.persist_draft(
                        connection, sale_id, draft
                    )) if draft is not None else None
                ),
            )
        except Exception:
            if draft is not None:
                try:
                    self.fiscal_sale_service.fiscal_service.release_number(
                        draft.reservation_id,
                        reason="A transação comercial da venda foi revertida.",
                    )
                except Exception:
                    # A falha principal precisa permanecer visível. Uma reserva
                    # não liberada expira de forma segura e nunca autoriza venda.
                    pass
            raise
        if draft is not None:
            self.last_fiscal_submission = {
                "sale_id": int(finalized.sale_id),
                "access_key": draft.access_key,
                "model": draft.model,
                "environment": draft.environment,
                "status": "ENFILEIRADO",
            }
        return PersistedCheckout(
            sale_id=int(finalized.sale_id),
            total=finalized.total,
            received=validation.received,
            change=finalized.change,
            payment_description=finalized.payment_description,
            status=finalized.status,
        )
