from __future__ import annotations

import dataclasses
import unittest
from datetime import date, datetime
from decimal import Decimal

from commercial.application.action_dto import ActionContext, ActionOrigin, ActionSensitivity
from commercial.application.commercial_action_service import CommercialActionService
from commercial.application.commercial_query_service import CommercialQueryService
from commercial.application.dto import CustomerRecord, ProductRecord
from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.ports import PersistedCheckout
from commercial.application.query_dto import (
    CancelledSaleSummary, DailyMovementSummary, DailySaleSummary,
    OverdueChargeSummary, ReceiptSummary,
)
from commercial.domain.payments import Payment, PaymentMethod


class Customers:
    record = CustomerRecord(
        8, "C8", "CLIENTE OITO", 88, Decimal("500.00"), Decimal("400.00")
    )
    def search(self, term, *, limit=30): return (self.record,) if term else ()
    def get(self, customer_id): return self.record if int(customer_id) == 8 else None


class Products:
    record = ProductRecord(4, "P4", "789", "PRODUTO", Decimal("25.00"))
    def search(self, term, *, limit=30): return (self.record,) if term else ()
    def get(self, product_id): return self.record if int(product_id) == 4 else None


class Reporting:
    def sales_for_day(self, day):
        return (DailySaleSummary(1, 8, "Venda", Decimal("25"), day.isoformat(), "PAGO", False),)
    def receipts_for_day(self, day):
        return (ReceiptSummary(2, 3, Decimal("25"), "PIX", day.isoformat(), "CLIENTE"),)
    def overdue_charges(self):
        return (OverdueChargeSummary(5, 8, "CLIENTE", 1, Decimal("10"), date(2026, 1, 1)),)
    def cancelled_sales_for_day(self, day):
        return (CancelledSaleSummary(6, 8, "Cancelada", Decimal("12"), day.isoformat()),)
    def movements_for_day(self, day):
        return (DailyMovementSummary(7, day.isoformat(), "CLIENTE", "COMPRA", "Venda", Decimal("25")),)


class CheckoutGateway:
    def __init__(self, error=None): self.error = error; self.calls = 0
    def checkout(self, command, *, customer, user):
        self.calls += 1
        if self.error: raise self.error
        return PersistedCheckout(31, command.final_total, command.final_total, Decimal("0"), "DINHEIRO", "PAGO")


class Cancellation:
    def __init__(self, error=None): self.error = error; self.calls = []
    def cancel(self, sale_id, *, user):
        from commercial.application.action_dto import PersistedCancellation
        self.calls.append((sale_id, user))
        if self.error: raise self.error
        return PersistedCancellation(int(sale_id))


class Events:
    def __init__(self, fail=False): self.fail = fail; self.events = []
    def sale_cancelled(self, event):
        self.events.append(event)
        if self.fail: raise RuntimeError("evento indisponível")


class CommercialQueryTests(unittest.TestCase):
    def setUp(self):
        self.query = CommercialQueryService(
            customers=Customers(), products=Products(), reporting=Reporting()
        )

    def test_customer_product_and_informative_credit(self):
        self.assertEqual(self.query.search_customers("oito")[0].customer_id, 8)
        self.assertEqual(self.query.get_customer(8).name, "CLIENTE OITO")
        credit = self.query.customer_credit(8)
        self.assertEqual(credit.available_credit, Decimal("100.00"))
        self.assertEqual(self.query.search_products("produto")[0].product_id, 4)
        self.assertEqual(self.query.get_product(4).unit_price, Decimal("25.00"))

    def test_daily_queries_return_immutable_dtos_with_decimal(self):
        selected = date(2026, 8, 22)
        groups = (
            self.query.daily_sales(selected), self.query.daily_receipts(selected),
            self.query.overdue_charges(), self.query.cancelled_sales(selected),
            self.query.daily_movements(selected),
        )
        for rows in groups:
            self.assertIsInstance(rows, tuple)
            self.assertTrue(dataclasses.is_dataclass(rows[0]))
            self.assertTrue(rows[0].__dataclass_params__.frozen)
        self.assertIsInstance(groups[0][0].total, Decimal)
        self.assertIsInstance(groups[1][0].amount, Decimal)
        self.assertIsInstance(groups[2][0].open_amount, Decimal)

    def test_missing_customer_credit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Cliente não encontrado"):
            self.query.customer_credit(999)


class CommercialActionTests(unittest.TestCase):
    def setUp(self):
        self.checkout_gateway = CheckoutGateway()
        self.pdv = PDVApplicationService(
            customers=Customers(), products=Products(), checkout_gateway=self.checkout_gateway
        )
        self.cancellation = Cancellation()
        self.events = Events()
        self.actions = CommercialActionService(
            pdv=self.pdv, cancellation=self.cancellation, events=self.events
        )
        self.context = ActionContext("operador", ActionOrigin.UI)

    def _session(self):
        session = self.pdv.new_session()
        self.pdv.select_customer(session, 8)
        self.pdv.add_loose_item(session, description="ITEM", quantity=1, unit_price=Decimal("25"))
        self.pdv.prepare_payments(session, (Payment(PaymentMethod.CASH, Decimal("25")),))
        return session

    def test_checkout_requires_confirmation_then_commits(self):
        session = self._session()
        pending = self.actions.checkout(session, context=self.context, confirmation_granted=False)
        self.assertFalse(pending.executed)
        self.assertEqual(pending.sensitivity, ActionSensitivity.CRITICAL)
        self.assertEqual(self.checkout_gateway.calls, 0)
        approved = self.actions.checkout(session, context=self.context, confirmation_granted=True)
        self.assertTrue(approved.committed)
        self.assertEqual(approved.resource_id, 31)
        self.assertEqual(approved.context.origin, ActionOrigin.UI)

    def test_checkout_refusal_preserves_non_committed_result(self):
        self.checkout_gateway.error = ValueError("Venda recusada")
        result = self.actions.checkout(self._session(), context=self.context, confirmation_granted=True)
        self.assertTrue(result.executed)
        self.assertFalse(result.committed)
        self.assertIn("recusada", result.message)

    def test_cancellation_sensitive_approved_and_invalid(self):
        pending = self.actions.cancel_sale(31, context=self.context, confirmation_granted=False)
        self.assertFalse(pending.executed)
        self.assertEqual(pending.sensitivity, ActionSensitivity.SENSITIVE)
        approved = self.actions.cancel_sale(31, context=self.context, confirmation_granted=True)
        self.assertTrue(approved.committed)
        self.assertEqual(self.cancellation.calls, [(31, "operador")])
        self.assertEqual(self.events.events[0].context.request_id, self.context.request_id)

        failed_actions = CommercialActionService(
            pdv=self.pdv, cancellation=Cancellation(ValueError("Venda não encontrada"))
        )
        refused = failed_actions.cancel_sale(999, context=self.context, confirmation_granted=True)
        self.assertFalse(refused.committed)
        self.assertIn("não encontrada", refused.message)

    def test_post_commit_event_failure_does_not_invite_duplicate(self):
        actions = CommercialActionService(
            pdv=self.pdv, cancellation=self.cancellation, events=Events(fail=True)
        )
        result = actions.cancel_sale(31, context=self.context, confirmation_granted=True)
        self.assertTrue(result.committed)
        self.assertTrue(result.secondary_effect_failed)
        self.assertIn("não repita", result.message)
        self.assertEqual(len(self.cancellation.calls), 1)

    def test_action_context_is_immutable_timezone_aware_and_keeps_ai_origin(self):
        context = ActionContext("assistente-autorizado", ActionOrigin.AI)
        self.assertEqual(context.origin, ActionOrigin.AI)
        self.assertIsNotNone(context.requested_at.tzinfo)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            context.origin = ActionOrigin.UI


if __name__ == "__main__":
    unittest.main()
