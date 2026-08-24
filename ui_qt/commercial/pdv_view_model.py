from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from commercial.application.dto import (
    BudgetDocument, CheckoutResult, CustomerRecord, ProductRecord, SuspendedSale,
)
from commercial.application.query_dto import DailySaleSummary
from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.pdv_session import PDVSession
from commercial.domain.money import MoneyCodec
from commercial.domain.payments import Payment, PaymentMethod


@dataclass(frozen=True, slots=True)
class CheckoutInput:
    method: PaymentMethod | None = None
    amount: Decimal = Decimal("0.00")
    payments: tuple[Payment, ...] = ()
    card_authorization: str = ""
    discount: Decimal = Decimal("0.00")
    discount_type: str = "VALUE"
    surcharge: Decimal = Decimal("0.00")
    surcharge_type: str = "VALUE"
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
        self.assistant_payment_method: PaymentMethod | None = None

    def load_assistant_draft(self, draft, authorization) -> None:
        """Transfere rascunho para uma sessão nova, sem checkout ou persistência."""
        # Importação tardia mantém edições sem IA (como FICHÁRIO) independentes.
        from assistant_nabi.confirmations import ConfirmedDraftAuthorization

        if not self.session.cart.is_empty:
            raise ValueError("Esvazie ou suspenda a venda atual antes de carregar o rascunho da Nabi.")
        temporary = self.application.new_session()
        customer = (
            self.application.select_customer(temporary, draft.customer_id)
            if draft.customer_id is not None
            else self.application.select_final_consumer(temporary)
        )
        for item in draft.items:
            current = self.application.get_product(item.product_id)
            if current is None or not current.active or current.unit_price != item.unit_price:
                raise ValueError(
                    f"O produto {item.code} mudou depois do rascunho. Revise novamente."
                )
            self.application.add_product(
                temporary, item.product_id, quantity=item.quantity
            )
        methods = {
            "DINHEIRO": PaymentMethod.CASH,
            "PIX": PaymentMethod.PIX,
            "DEBITO": PaymentMethod.DEBIT,
            "CREDITO": PaymentMethod.CREDIT_CARD,
            "CREDIARIO": PaymentMethod.STORE_CREDIT,
            "OUTROS": PaymentMethod.OTHER,
        }
        payment_method = methods[draft.payment_method]
        if not isinstance(authorization, ConfirmedDraftAuthorization):
            raise PermissionError("O rascunho da Nabi exige autorização confirmada.")
        authorization.consume(draft, operation="SALE")
        self.session = temporary
        self.selected_customer = customer
        self.selected_product = None
        self.assistant_payment_method = payment_method

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

    def search_products(self, term: str, *, limit: int = 30) -> tuple[ProductRecord, ...]:
        return self.application.search_products(term, limit=limit)

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

    def edit_item(
        self,
        line_id: str,
        *,
        quantity: str,
        unit_price: Decimal,
        discount_percent: Decimal,
    ) -> None:
        self.application.edit_item(
            self.session,
            line_id,
            quantity=self.parse_quantity(quantity),
            unit_price=unit_price,
            discount_percent=discount_percent,
        )

    def save_budget(self) -> BudgetDocument:
        budget = self.application.save_budget(self.session)
        self.selected_customer = None
        self.selected_product = None
        return budget

    def list_budgets(self) -> tuple[BudgetDocument, ...]:
        return self.application.list_budgets()

    def load_budget(self, budget_id: str, *, replace: bool = False) -> BudgetDocument:
        budget = self.application.load_budget(self.session, budget_id, replace=replace)
        self.selected_customer = self.application.get_customer(budget.customer_id)
        self.selected_product = None
        return budget

    def budget_preview_text(self, budget: BudgetDocument) -> str:
        return self.application.budget_preview_text(budget)

    def print_budget(self, budget: BudgetDocument) -> str:
        return self.application.print_budget(budget)

    def generate_budget_pdf(self, budget: BudgetDocument) -> str:
        return self.application.generate_budget_pdf(budget)

    def suspend_sale(self) -> SuspendedSale:
        suspended = self.application.suspend_sale(self.session)
        self.selected_customer = None
        self.selected_product = None
        return suspended

    def list_suspended_sales(self) -> tuple[SuspendedSale, ...]:
        return self.application.list_suspended_sales()

    def resume_suspended_sale(
        self, suspended_id: str, *, replace: bool = False
    ) -> SuspendedSale:
        suspended = self.application.resume_suspended_sale(
            self.session, suspended_id, replace=replace
        )
        self.selected_customer = (
            self.application.get_customer(suspended.customer_id)
            if suspended.customer_id is not None else None
        )
        self.selected_product = None
        return suspended

    def list_daily_sales(self) -> tuple[DailySaleSummary, ...]:
        return self.application.list_daily_sales()

    def daily_sale_preview_text(self, sale: DailySaleSummary) -> str:
        return self.application.daily_sale_preview_text(sale)

    def print_daily_sale(self, sale: DailySaleSummary) -> str:
        return self.application.print_daily_sale(sale)

    def generate_daily_sale_pdf(self, sale: DailySaleSummary) -> str:
        return self.application.generate_daily_sale_pdf(sale)

    def cancel_daily_sale(self, sale_id: int, *, user: str = "Sistema") -> None:
        self.application.cancel_daily_sale(sale_id, user=user)

    @staticmethod
    def _payments(data: CheckoutInput) -> tuple[Payment, ...]:
        if data.payments:
            return tuple(data.payments)
        if data.method is None:
            raise ValueError("Informe ao menos uma forma de pagamento.")
        if data.method is PaymentMethod.STORE_CREDIT:
            entrance: tuple[Payment, ...] = ()
            if data.entrance_amount > MoneyCodec.ZERO:
                if data.entrance_method in {None, PaymentMethod.STORE_CREDIT}:
                    raise ValueError("Informe uma forma válida para a entrada.")
                entrance = (Payment(data.entrance_method, data.entrance_amount),)
            return (*entrance, Payment(PaymentMethod.STORE_CREDIT, data.amount))
        return (Payment(data.method, data.amount, data.card_authorization),)

    def preview_checkout(self, data: CheckoutInput):
        return self.application.configure_checkout(
            self.session,
            payments=self._payments(data),
            discount=data.discount,
            discount_type=data.discount_type,
            surcharge=data.surcharge,
            surcharge_type=data.surcharge_type,
            installment_count=data.installment_count,
            first_due_date=data.first_due_date,
            apply=False,
        )

    def checkout(self, data: CheckoutInput, *, user: str) -> CheckoutResult:
        self.application.configure_checkout(
            self.session,
            payments=self._payments(data),
            discount=data.discount,
            discount_type=data.discount_type,
            surcharge=data.surcharge,
            surcharge_type=data.surcharge_type,
            installment_count=data.installment_count,
            first_due_date=data.first_due_date,
        )
        result = self.application.checkout(self.session, user=user)
        if result.session_consumed:
            self.selected_customer = None
            self.selected_product = None
            self.assistant_payment_method = None
        return result
