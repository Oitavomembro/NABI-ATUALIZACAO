from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from assistant_nabi import CapabilityLevel, ModelReply, ToolRequest, create_draft_assistant
from assistant_nabi.customer_receipt_drafts import CustomerReceiptDraftService
from assistant_nabi.customer_receipt_gateway import NabiCodeCustomerReceiptAssistantGateway


class Security:
    session = SimpleNamespace(user=SimpleNamespace(username="caixa", profile="ADMIN", active=True))
    def is_expired(self): return False
    def require(self, module, action): return (module, action) in {
        ("financeiro", "pay"), ("clientes", "view"),
        ("produtos", "view"), ("vendas", "create"),
    }


class Audit:
    def record_event(self, *args, **kwargs): pass
    def record_event_strict(self, *args, **kwargs): pass


class Queries:
    def search_products(self, term, *, limit): return ()
    def search_customers(self, term, *, limit): return ()


class Customers:
    def __init__(self): self.balance = Decimal("203.00")
    def get_customer(self, customer_id):
        return SimpleNamespace(
            customer_id=customer_id, record_number=3321,
            name="GUSTAVO", debt_balance=self.balance,
        )


class Actions:
    def __init__(self, customers): self.customers = customers; self.calls = []
    def receive_customer_payment(self, command, **kwargs):
        self.calls.append((command, kwargs))
        self.customers.balance -= command.amount
        return SimpleNamespace(committed=True, message="ok", resource_id=91)


class Model:
    def respond(self, message, *, available_tools):
        return ModelReply("Recebimento preparado.", (ToolRequest(
            "clientes.preparar_recebimento", {
                "customer_id": 7, "amount": "100.00", "payment_method": "PIX",
                "payment_date": "2026-08-24", "notes": "Pagamento no caixa",
            }
        ),))


class CustomerReceiptAssistantTests(unittest.TestCase):
    def test_rascunho_rejeita_excesso_e_nao_altera_saldo(self):
        customers = Customers()
        service = CustomerReceiptDraftService(customers)
        draft = service.create(
            customer_id=7, amount="100", payment_method="PIX",
            payment_date="2026-08-24",
        )
        self.assertEqual(draft.previous_balance, Decimal("203.00"))
        self.assertEqual(draft.expected_balance, Decimal("103.00"))
        self.assertEqual(customers.balance, Decimal("203.00"))
        with self.assertRaisesRegex(ValueError, "ultrapassar"):
            service.create(
                customer_id=7, amount="204", payment_method="PIX",
                payment_date="2026-08-24",
            )

    def test_confirma_revalida_saldo_e_executa_uma_vez(self):
        customers = Customers(); actions = Actions(customers)
        drafts = CustomerReceiptDraftService(customers)
        assistant = create_draft_assistant(
            model=Model(), query_service=Queries(), security_service=Security(),
            audit_service=Audit(), session_id="sessao-real",
            customer_receipt_draft_service=drafts,
            customer_receipt_executor=NabiCodeCustomerReceiptAssistantGateway(
                actions, customers
            ),
        )
        prepared = assistant.ask("Receba cem reais").tool_results[0]
        self.assertTrue(prepared.success)
        self.assertFalse(prepared.payload["persisted"])
        challenge = assistant.review_draft(
            prepared.payload["draft_id"], prepared.payload["fingerprint"]
        )
        self.assertIs(challenge.required_capability, CapabilityLevel.REINFORCED_CONFIRMATION)
        result, _authorization = assistant.confirm_and_execute_customer_receipt(
            challenge.token, prepared.payload["draft_id"], prepared.payload["fingerprint"]
        )
        self.assertEqual(result.resource_id, 91)
        self.assertEqual(len(actions.calls), 1)
        self.assertEqual(actions.calls[0][1]["operation_fingerprint"], prepared.payload["fingerprint"])

    def test_saldo_alterado_depois_da_revisao_bloqueia(self):
        customers = Customers(); actions = Actions(customers)
        drafts = CustomerReceiptDraftService(customers)
        assistant = create_draft_assistant(
            model=Model(), query_service=Queries(), security_service=Security(),
            audit_service=Audit(), session_id="sessao-real",
            customer_receipt_draft_service=drafts,
            customer_receipt_executor=NabiCodeCustomerReceiptAssistantGateway(actions, customers),
        )
        prepared = assistant.ask("Prepare").tool_results[0]
        challenge = assistant.review_draft(prepared.payload["draft_id"], prepared.payload["fingerprint"])
        customers.balance = Decimal("180.00")
        with self.assertRaisesRegex(ValueError, "saldo.*mudou"):
            assistant.confirm_and_execute_customer_receipt(
                challenge.token, prepared.payload["draft_id"], prepared.payload["fingerprint"]
            )
        self.assertEqual(actions.calls, [])


if __name__ == "__main__": unittest.main()
