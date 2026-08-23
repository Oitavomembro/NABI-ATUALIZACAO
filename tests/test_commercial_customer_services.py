from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.commercial_action_service import CommercialActionService
from commercial.application.customer_dto import CustomerReceiptCommand, PersistedCustomerReceipt


class UnusedPDV:
    pass


class UnusedCancellation:
    def cancel(self, sale_id, *, user):
        raise AssertionError("cancelamento não deveria ser chamado")


class ReceiptPort:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def receive(self, command, *, user):
        self.calls.append((command, user))
        if self.error:
            raise self.error
        return PersistedCustomerReceipt(
            movement_id=90, customer_id=command.customer_id, amount=command.amount,
            previous_balance=Decimal("500.00"), new_balance=Decimal("300.00"),
            payment_method=command.payment_method,
        )


class ReceiptEvents:
    def __init__(self, fail=False):
        self.fail = fail
        self.events = []

    def customer_payment_received(self, event):
        self.events.append(event)
        if self.fail:
            raise RuntimeError("evento indisponível")


class CustomerReceiptActionTests(unittest.TestCase):
    def setUp(self):
        self.port = ReceiptPort()
        self.events = ReceiptEvents()
        self.service = CommercialActionService(
            pdv=UnusedPDV(), cancellation=UnusedCancellation(),
            customer_receipts=self.port, events=self.events,
        )
        self.context = ActionContext("caixa", ActionOrigin.UI)
        self.command = CustomerReceiptCommand(
            customer_id=7, amount=Decimal("200"), payment_method="PIX",
            payment_date=date(2026, 8, 22),
        )

    def test_requires_confirmation_and_preserves_customer_id(self):
        pending = self.service.receive_customer_payment(
            self.command, context=self.context, confirmation_granted=False
        )
        self.assertFalse(pending.executed)
        self.assertEqual(self.port.calls, [])
        result = self.service.receive_customer_payment(
            self.command, context=self.context, confirmation_granted=True
        )
        self.assertTrue(result.committed)
        self.assertEqual(self.port.calls[0][0].customer_id, 7)
        self.assertEqual(self.events.events[0].request_id, self.context.request_id)

    def test_backend_failure_is_not_committed(self):
        service = CommercialActionService(
            pdv=UnusedPDV(), cancellation=UnusedCancellation(),
            customer_receipts=ReceiptPort(ValueError("Saldo insuficiente")),
        )
        result = service.receive_customer_payment(
            self.command, context=self.context, confirmation_granted=True
        )
        self.assertTrue(result.executed)
        self.assertFalse(result.committed)
        self.assertIn("Saldo", result.message)

    def test_event_failure_after_commit_does_not_allow_duplicate(self):
        events = ReceiptEvents(fail=True)
        service = CommercialActionService(
            pdv=UnusedPDV(), cancellation=UnusedCancellation(),
            customer_receipts=self.port, events=events,
        )
        result = service.receive_customer_payment(
            self.command, context=self.context, confirmation_granted=True
        )
        self.assertTrue(result.committed)
        self.assertTrue(result.secondary_effect_failed)
        self.assertIn("não registre novamente", result.message)
        self.assertEqual(len(self.port.calls), 1)


if __name__ == "__main__":
    unittest.main()
