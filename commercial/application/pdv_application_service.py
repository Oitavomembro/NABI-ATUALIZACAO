from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from commercial.domain.cart import CartItem
from commercial.domain.credit import CreditTerms
from commercial.domain.payments import Payment, PaymentMethod, PaymentPlan

from .dto import CheckoutCommand, CheckoutReceipt, CheckoutResult, CustomerRecord, ProductRecord
from .pdv_session import PDVSession
from .ports import CheckoutPort, CommercialEventPort, CustomerLookupPort, ProductLookupPort


class PDVApplicationService:
    """API comercial do PDV, independente de UI e persistência concreta."""

    def __init__(
        self,
        *,
        customers: CustomerLookupPort,
        products: ProductLookupPort,
        checkout_gateway: CheckoutPort,
        events: CommercialEventPort | None = None,
    ) -> None:
        self.customers = customers
        self.products = products
        self.checkout_gateway = checkout_gateway
        self.events = events

    @staticmethod
    def new_session() -> PDVSession:
        return PDVSession()

    def search_customers(self, term: str, *, limit: int = 30) -> tuple[CustomerRecord, ...]:
        return self.customers.search(term, limit=limit)

    def get_customer(self, customer_id: int) -> CustomerRecord | None:
        return self.customers.get(customer_id)

    def select_customer(self, session: PDVSession, customer_id: int) -> CustomerRecord:
        customer = self.get_customer(customer_id)
        if customer is None:
            raise ValueError("Cliente não encontrado.")
        session.select_customer(customer.customer_id)
        return customer

    @staticmethod
    def clear_customer(session: PDVSession) -> None:
        session.clear_customer()

    def search_products(self, term: str, *, limit: int = 30) -> tuple[ProductRecord, ...]:
        return self.products.search(term, limit=limit)

    def get_product(self, product_id: int) -> ProductRecord | None:
        return self.products.get(product_id)

    def add_product(
        self,
        session: PDVSession,
        product_id: int,
        *,
        quantity: Decimal | int | str = Decimal("1"),
        discount_percent: Decimal | int | str = Decimal("0"),
    ) -> CartItem:
        product = self.get_product(product_id)
        if product is None or not product.active:
            raise ValueError("Produto não encontrado ou inativo.")
        return session.add_item(
            CartItem(
                product_id=product.product_id,
                description=product.description,
                quantity=quantity,
                unit_price=product.unit_price,
                discount_percent=discount_percent,
            )
        )

    @staticmethod
    def add_loose_item(
        session: PDVSession,
        *,
        description: str,
        quantity: Decimal | int | str,
        unit_price: Decimal | int | str,
        discount_percent: Decimal | int | str = Decimal("0"),
    ) -> CartItem:
        return session.add_item(
            CartItem(
                product_id=None,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                discount_percent=discount_percent,
            )
        )

    @staticmethod
    def remove_item(session: PDVSession, line_id: str) -> CartItem:
        return session.remove_item(line_id)

    @staticmethod
    def change_quantity(
        session: PDVSession, line_id: str, quantity: Decimal | int | str
    ) -> CartItem:
        return session.change_quantity(line_id, quantity)

    @staticmethod
    def change_unit_price(
        session: PDVSession,
        line_id: str,
        unit_price: Decimal | int | str,
        *,
        allowed: bool,
    ) -> CartItem:
        return session.change_unit_price(line_id, unit_price, allowed=allowed)

    @staticmethod
    def set_adjustments(
        session: PDVSession,
        *,
        discount_amount: Decimal | int | str = Decimal("0.00"),
        surcharge_amount: Decimal | int | str = Decimal("0.00"),
    ) -> None:
        session.set_adjustments(
            discount_amount=discount_amount,
            surcharge_amount=surcharge_amount,
        )

    @staticmethod
    def prepare_payments(session: PDVSession, payments: Iterable[Payment]) -> PaymentPlan:
        plan = PaymentPlan(payments)
        if plan.has_store_credit:
            raise ValueError("Use prepare_store_credit para pagamentos com crediário.")
        session.set_payment_plan(plan)
        return plan

    @staticmethod
    def prepare_store_credit(
        session: PDVSession,
        *,
        entrance_payments: Iterable[Payment],
        financed_value: Decimal | int | str,
        due_dates: Iterable[date],
    ) -> CreditTerms:
        entrance = tuple(entrance_payments)
        if any(payment.method is PaymentMethod.STORE_CREDIT for payment in entrance):
            raise ValueError("A entrada não pode conter outra parte em crediário.")
        plan = PaymentPlan(
            (*entrance, Payment(PaymentMethod.STORE_CREDIT, financed_value))
        )
        plan.validate_against(session.total)
        terms = CreditTerms.create(
            down_payment=plan.entrance_value(session.total),
            financed_value=plan.financed_value,
            due_dates=due_dates,
        )
        session.set_payment_plan(plan, credit_terms=terms)
        return terms

    @classmethod
    def prepare_store_credit_schedule(
        cls,
        session: PDVSession,
        *,
        entrance_payments: Iterable[Payment],
        financed_value: Decimal | int | str,
        installment_count: int,
        first_due_date: date,
    ) -> CreditTerms:
        """Cria o cronograma comercial fora de qualquer camada visual."""

        count = int(installment_count)
        if count <= 0:
            raise ValueError("A quantidade de parcelas deve ser maior que zero.")
        if not isinstance(first_due_date, date):
            raise ValueError("O primeiro vencimento é inválido.")
        return cls.prepare_store_credit(
            session,
            entrance_payments=entrance_payments,
            financed_value=financed_value,
            due_dates=tuple(
                first_due_date + timedelta(days=30 * index)
                for index in range(count)
            ),
        )

    @staticmethod
    def prepare_checkout(session: PDVSession) -> CheckoutCommand:
        return session.build_checkout_command()

    @staticmethod
    def _safe_failure_message(error: Exception) -> str:
        if isinstance(error, ValueError):
            return str(error) or "A venda foi recusada por uma regra comercial."
        return "Não foi possível concluir a venda. Nenhuma venda foi confirmada."

    @staticmethod
    def _failed_result(session: PDVSession, error: Exception) -> CheckoutResult:
        plan = session.payment_plan
        financed = plan.financed_value if plan is not None else Decimal("0.00")
        received = plan.total if plan is not None else Decimal("0.00")
        return CheckoutResult(
            success=False,
            committed=False,
            sale_id=None,
            total=max(Decimal("0.00"), session.total),
            financed_value=financed,
            received=received,
            change=Decimal("0.00"),
            message=PDVApplicationService._safe_failure_message(error),
            status="REJEITADO",
            session_consumed=False,
        )

    def checkout(self, session: PDVSession, *, user: str) -> CheckoutResult:
        try:
            command = self.prepare_checkout(session)
            customer = self.get_customer(command.customer_id)
            if customer is None:
                raise ValueError("Cliente não encontrado.")
            session.begin_checkout()
            persisted = self.checkout_gateway.checkout(
                command,
                customer=customer,
                user=str(user or "Sistema").strip() or "Sistema",
            )
        except Exception as error:
            session.checkout_failed()
            return self._failed_result(session, error)

        # O contrato de CheckoutPort garante que o retorno só ocorre após commit.
        # A sessão é consumida antes de qualquer efeito secundário.
        session.consume_after_commit()
        receipt = CheckoutReceipt(
            sale_id=persisted.sale_id,
            customer=customer,
            items=command.items,
            payments=command.payment_plan.payments,
            total=persisted.total,
            financed_value=command.payment_plan.financed_value,
            received=persisted.received,
            change=persisted.change,
            payment_description=persisted.payment_description,
            status=persisted.status,
        )
        result = CheckoutResult(
            success=True,
            committed=True,
            sale_id=persisted.sale_id,
            total=persisted.total,
            financed_value=command.payment_plan.financed_value,
            received=persisted.received,
            change=persisted.change,
            message=f"Venda #{persisted.sale_id} confirmada.",
            status=persisted.status,
            session_consumed=True,
            receipt=receipt,
        )
        if self.events is not None:
            try:
                self.events.sale_committed(result)
            except Exception:
                result = replace(
                    result,
                    message=(
                        f"Venda #{persisted.sale_id} confirmada, mas um efeito secundário "
                        "não pôde ser concluído. Não finalize novamente."
                    ),
                    secondary_effect_failed=True,
                )
        return result
