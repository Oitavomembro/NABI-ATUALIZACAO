from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from commercial.domain.cart import CartItem
from commercial.domain.credit import CreditTerms
from commercial.domain.money import MoneyCodec
from commercial.domain.payments import Payment, PaymentMethod, PaymentPlan

from .dto import (
    BudgetDocument, CheckoutCommand, CheckoutReceipt, CheckoutResult, CustomerRecord,
    ProductRecord, SuspendedSale,
)
from .pdv_session import PDVSession
from .ports import (
    BudgetOutputPort, BudgetPort, CheckoutPort, CommercialEventPort, CustomerLookupPort,
    DailySalesPort, ProductLookupPort, SaleReceiptOutputPort, SuspendedSalePort,
)
from .query_dto import DailySaleSummary


class PDVApplicationService:
    """API comercial do PDV, independente de UI e persistência concreta."""

    def __init__(
        self,
        *,
        customers: CustomerLookupPort,
        products: ProductLookupPort,
        checkout_gateway: CheckoutPort,
        events: CommercialEventPort | None = None,
        receipt_output: SaleReceiptOutputPort | None = None,
        budgets: BudgetPort | None = None,
        budget_output: BudgetOutputPort | None = None,
        suspended_sales: SuspendedSalePort | None = None,
        daily_sales: DailySalesPort | None = None,
    ) -> None:
        self.customers = customers
        self.products = products
        self.checkout_gateway = checkout_gateway
        self.events = events
        self.receipt_output = receipt_output
        self.budgets = budgets
        self.budget_output = budget_output
        self.suspended_sales = suspended_sales
        self.daily_sales = daily_sales

    def _daily_sales_port(self) -> DailySalesPort:
        if self.daily_sales is None:
            raise RuntimeError("O serviço de vendas do dia não está configurado.")
        return self.daily_sales

    def list_daily_sales(self) -> tuple[DailySaleSummary, ...]:
        return self._daily_sales_port().list_today()

    def daily_sale_preview_text(self, sale: DailySaleSummary) -> str:
        return self._daily_sales_port().preview_text(sale)

    def print_daily_sale(self, sale: DailySaleSummary) -> str:
        return self._daily_sales_port().print_thermal(sale)

    def generate_daily_sale_pdf(self, sale: DailySaleSummary) -> str:
        path = self._daily_sales_port().generate_pdf(sale)
        self._daily_sales_port().open_file(path)
        return path

    def cancel_daily_sale(self, sale_id: int, *, user: str) -> None:
        self._daily_sales_port().cancel_local(sale_id, user=user)

    def _suspended_sale_port(self) -> SuspendedSalePort:
        if self.suspended_sales is None:
            raise RuntimeError("O serviço de vendas suspensas não está configurado.")
        return self.suspended_sales

    def suspend_sale(self, session: PDVSession) -> SuspendedSale:
        session.ensure_open()
        if session.cart.is_empty:
            raise ValueError("Inclua ao menos um item antes de suspender a venda.")
        customer = None
        if session.customer_id is not None:
            customer = self.get_customer(session.customer_id)
            if customer is None:
                raise ValueError("O cliente selecionado não está mais disponível.")
        suspended = self._suspended_sale_port().suspend(
            customer_id=customer.customer_id if customer else None,
            customer_name=customer.name if customer else "",
            items=session.cart.items,
        )
        session.reset()
        return suspended

    def list_suspended_sales(self) -> tuple[SuspendedSale, ...]:
        return self._suspended_sale_port().list_open()

    def resume_suspended_sale(
        self, session: PDVSession, suspended_id: str, *, replace: bool = False
    ) -> SuspendedSale:
        session.ensure_open()
        if not session.cart.is_empty and not replace:
            raise ValueError("O carrinho atual precisa ser preservado ou substituído explicitamente.")
        suspended = next(
            (item for item in self.list_suspended_sales()
             if item.suspended_id == str(suspended_id)), None
        )
        if suspended is None:
            raise ValueError("Venda suspensa não encontrada.")
        customer = None
        if suspended.customer_id is not None:
            customer = self.get_customer(suspended.customer_id)
            if customer is None:
                raise ValueError("O cliente da venda suspensa não está mais disponível.")
        resumed = self._suspended_sale_port().resume(suspended.suspended_id)
        session.reset()
        for item in resumed.items:
            session.add_item(item)
        if customer is not None:
            session.select_customer(customer.customer_id)
        return resumed

    def _budget_port(self) -> BudgetPort:
        if self.budgets is None:
            raise RuntimeError("O serviço de orçamentos não está configurado.")
        return self.budgets

    def save_budget(self, session: PDVSession) -> BudgetDocument:
        session.ensure_open()
        if session.cart.is_empty:
            raise ValueError("Inclua ao menos um item antes de salvar o orçamento.")
        customer = (
            self.select_final_consumer(session)
            if session.customer_id is None
            else self.get_customer(session.customer_id)
        )
        if customer is None:
            raise ValueError("O cliente do orçamento não está disponível.")
        budget = self._budget_port().save(
            customer_id=customer.customer_id,
            customer_name=customer.name,
            items=session.cart.items,
        )
        session.reset()
        return budget

    def list_budgets(self) -> tuple[BudgetDocument, ...]:
        return self._budget_port().list_open()

    def load_budget(
        self, session: PDVSession, budget_id: str, *, replace: bool = False
    ) -> BudgetDocument:
        session.ensure_open()
        if not session.cart.is_empty and not replace:
            raise ValueError("O carrinho atual precisa ser preservado ou substituído explicitamente.")
        budget = next(
            (item for item in self.list_budgets() if item.budget_id == str(budget_id)), None
        )
        if budget is None:
            raise ValueError("Orçamento não encontrado.")
        customer = self.get_customer(budget.customer_id)
        if customer is None:
            raise ValueError("O cliente do orçamento não está mais disponível.")
        consumed = self._budget_port().consume(budget.budget_id)
        session.reset()
        for item in consumed.items:
            session.add_item(item)
        session.select_customer(customer.customer_id)
        return consumed

    def budget_preview_text(self, budget: BudgetDocument) -> str:
        if self.budget_output is None:
            raise RuntimeError("A saída de orçamento não está configurada.")
        return self.budget_output.preview_text(budget)

    def print_budget(self, budget: BudgetDocument) -> str:
        if self.budget_output is None:
            raise RuntimeError("A impressão de orçamento não está configurada.")
        return self.budget_output.print_thermal(budget)

    def generate_budget_pdf(self, budget: BudgetDocument) -> str:
        if self.budget_output is None:
            raise RuntimeError("A geração de PDF de orçamento não está configurada.")
        path = self.budget_output.generate_pdf(budget)
        self.budget_output.open_file(path)
        return path

    @staticmethod
    def _confirmed_receipt(result: CheckoutResult) -> CheckoutReceipt:
        if not result.committed or not result.session_consumed or result.receipt is None:
            raise ValueError("O comprovante exige uma venda confirmada.")
        return result.receipt

    def print_receipt(self, result: CheckoutResult) -> str:
        if self.receipt_output is None:
            raise RuntimeError("A impressão de comprovante não está configurada.")
        return self.receipt_output.print_thermal(self._confirmed_receipt(result))

    def generate_receipt_pdf(self, result: CheckoutResult) -> str:
        if self.receipt_output is None:
            raise RuntimeError("A geração de PDF não está configurada.")
        path = self.receipt_output.generate_pdf(self._confirmed_receipt(result))
        self.receipt_output.open_file(path)
        return path

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

    def select_final_consumer(self, session: PDVSession) -> CustomerRecord:
        customer = self.customers.get_final_consumer()
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
    def edit_item(
        session: PDVSession,
        line_id: str,
        *,
        quantity: Decimal | int | str,
        unit_price: Decimal | int | str,
        discount_percent: Decimal | int | str,
        allow_registered_price_change: bool = False,
    ) -> CartItem:
        current = next(
            (item for item in session.cart.items if item.line_id == line_id), None
        )
        if current is None:
            raise KeyError("Item não encontrado no carrinho.")
        return session.edit_item(
            line_id,
            quantity=quantity,
            unit_price=unit_price,
            discount_percent=discount_percent,
            allow_price_change=current.is_loose or allow_registered_price_change,
        )

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
    def resolve_adjustments(
        items_total: Decimal,
        *,
        discount: Decimal | int | str = Decimal("0"),
        discount_type: str = "VALUE",
        surcharge: Decimal | int | str = Decimal("0"),
        surcharge_type: str = "VALUE",
    ) -> tuple[Decimal, Decimal, Decimal]:
        base_total = MoneyCodec.parse(items_total, field="subtotal")
        discount_input = MoneyCodec.parse(discount, field="desconto")
        surcharge_input = MoneyCodec.parse(surcharge, field="acréscimo")
        if discount_input < 0 or surcharge_input < 0:
            raise ValueError("Desconto e acréscimo não podem ser negativos.")
        discount_kind = str(discount_type).strip().upper()
        surcharge_kind = str(surcharge_type).strip().upper()
        if discount_kind not in {"VALUE", "PERCENT"} or surcharge_kind not in {"VALUE", "PERCENT"}:
            raise ValueError("Tipo de ajuste inválido.")
        if discount_kind == "PERCENT":
            if discount_input > 100:
                raise ValueError("O desconto percentual não pode ultrapassar 100%.")
            discount_amount = (base_total * discount_input / Decimal("100")).quantize(
                MoneyCodec.CENT, rounding=ROUND_HALF_UP
            )
        else:
            discount_amount = discount_input
        if discount_amount > base_total:
            raise ValueError("O desconto não pode ultrapassar o total da venda.")
        adjusted_base = base_total - discount_amount
        surcharge_amount = (
            adjusted_base * surcharge_input / Decimal("100")
            if surcharge_kind == "PERCENT"
            else surcharge_input
        ).quantize(MoneyCodec.CENT, rounding=ROUND_HALF_UP)
        final_total = (adjusted_base + surcharge_amount).quantize(MoneyCodec.CENT)
        if final_total <= 0:
            raise ValueError("O total final deve ser maior que zero.")
        return discount_amount, surcharge_amount, final_total

    @classmethod
    def configure_checkout(
        cls,
        session: PDVSession,
        *,
        payments: Iterable[Payment],
        discount: Decimal | int | str = Decimal("0"),
        discount_type: str = "VALUE",
        surcharge: Decimal | int | str = Decimal("0"),
        surcharge_type: str = "VALUE",
        installment_count: int = 1,
        first_due_date: date | None = None,
        apply: bool = True,
    ):
        discount_amount, surcharge_amount, final_total = cls.resolve_adjustments(
            session.items_total,
            discount=discount,
            discount_type=discount_type,
            surcharge=surcharge,
            surcharge_type=surcharge_type,
        )
        plan = PaymentPlan(tuple(payments))
        validation = plan.validate_against(final_total)
        terms = None
        if plan.has_store_credit:
            count = int(installment_count)
            if count <= 0:
                raise ValueError("A quantidade de parcelas deve ser maior que zero.")
            due = first_due_date or date.today() + timedelta(days=30)
            terms = CreditTerms.create(
                down_payment=plan.entrance_value(final_total),
                financed_value=plan.financed_value,
                due_dates=tuple(due + timedelta(days=30 * index) for index in range(count)),
            )
        if apply:
            session.set_adjustments(
                discount_amount=discount_amount, surcharge_amount=surcharge_amount
            )
            session.set_payment_plan(plan, credit_terms=terms)
        return plan, validation, terms, discount_amount, surcharge_amount, final_total

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
