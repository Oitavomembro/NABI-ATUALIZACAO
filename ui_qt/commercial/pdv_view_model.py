from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from commercial.application.dto import CheckoutResult, CustomerRecord, ProductRecord
from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.pdv_session import PDVSession
from commercial.domain.money import MoneyCodec
from commercial.domain.payments import Payment, PaymentMethod


@dataclass(frozen=True, slots=True)
class CheckoutInput:
    method: PaymentMethod
    amount: Decimal
    entrance_method: PaymentMethod | None = None
    entrance_amount: Decimal = Decimal("0.00")
    installment_count: int = 1
    first_due_date: date | None = None


class PDVViewModel:
    """Traduz ações visuais para a API comercial, sem SQL ou regras de crédito."""

    def __init__(self, application: PDVApplicationService) -> None:
        self.application = application
        self.session = application.new_session()
        self.selected_customer: CustomerRecord | None = None
        self.selected_product: ProductRecord | None = None

    @property
    def total(self) -> Decimal:
        return self.session.total

    def search_customers(self, term: str) -> tuple[CustomerRecord, ...]:
        return self.application.search_customers(term)

    def select_customer(self, customer_id: int) -> CustomerRecord:
        self.selected_customer = self.application.select_customer(self.session, customer_id)
        return self.selected_customer

    def select_final_consumer(self) -> CustomerRecord:
        self.selected_customer = self.application.select_final_consumer(self.session)
        return self.selected_customer

    def clear_customer(self) -> None:
        self.application.clear_customer(self.session)
        self.selected_customer = None

    def search_products(self, term: str) -> tuple[ProductRecord, ...]:
        return self.application.search_products(term)

    def select_product(self, product_id: int) -> ProductRecord:
        product = self.application.get_product(product_id)
        if product is None or not product.active:
            raise ValueError("Produto não encontrado ou inativo.")
        self.selected_product = product
        return product

    def clear_product(self) -> None:
        self.selected_product = None

    @staticmethod
    def parse_quantity(text: str) -> Decimal:
        normalized = str(text).strip().replace(",", ".")
        try:
            quantity = Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError("Quantidade inválida.") from exc
        if not quantity.is_finite() or quantity <= 0 or quantity.as_tuple().exponent < -4:
            raise ValueError("A quantidade deve ser positiva e ter até quatro casas decimais.")
        return quantity

    def add_selected_product(self, quantity: str) -> None:
        if self.selected_product is None:
            raise ValueError("Selecione um produto cadastrado.")
        self.application.add_product(
            self.session,
            self.selected_product.product_id,
            quantity=self.parse_quantity(quantity),
        )

    def add_loose_item(self, description: str, quantity: str, unit_price: Decimal) -> None:
        self.application.add_loose_item(
            self.session,
            description=description,
            quantity=self.parse_quantity(quantity),
            unit_price=unit_price,
        )

    def remove_item(self, line_id: str) -> None:
        self.application.remove_item(self.session, line_id)

    def checkout(self, data: CheckoutInput, *, user: str) -> CheckoutResult:
        if data.method is PaymentMethod.STORE_CREDIT:
            entrance: tuple[Payment, ...] = ()
            if data.entrance_amount > MoneyCodec.ZERO:
                if data.entrance_method in {None, PaymentMethod.STORE_CREDIT}:
                    raise ValueError("Informe uma forma válida para a entrada.")
                entrance = (Payment(data.entrance_method, data.entrance_amount),)
            first_due = data.first_due_date or date.today() + timedelta(days=30)
            self.application.prepare_store_credit_schedule(
                self.session,
                entrance_payments=entrance,
                financed_value=data.amount,
                installment_count=data.installment_count,
                first_due_date=first_due,
            )
        else:
            self.application.prepare_payments(
                self.session, (Payment(data.method, data.amount),)
            )
        result = self.application.checkout(self.session, user=user)
        if result.session_consumed:
            self.selected_customer = None
            self.selected_product = None
        return result
