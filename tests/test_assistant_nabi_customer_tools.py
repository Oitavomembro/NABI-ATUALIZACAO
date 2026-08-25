from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from assistant_nabi import CapabilityLevel, ModelReply, ToolRequest, create_draft_assistant
from assistant_nabi.customer_drafts import CustomerRegistrationDraftService
from assistant_nabi.customer_gateway import NabiCodeCustomerRegistrationGateway
from assistant_nabi.customer_tools import PREPARE_CUSTOMER_REGISTRATION


class Security:
    session = SimpleNamespace(user=SimpleNamespace(username="op", profile="OPERADOR", active=True))
    def is_expired(self): return False
    def require(self, module, action): return (module, action) in {
        ("clientes", "create"), ("clientes", "view"),
        ("produtos", "view"), ("vendas", "create"),
    }


class Audit:
    def __init__(self): self.events = []
    def record_event(self, *args, **kwargs): self.events.append((args, kwargs))
    def record_event_strict(self, *args, **kwargs): self.events.append((args, kwargs))


class Queries:
    def search_products(self, term, *, limit): return ()
    def search_customers(self, term, *, limit): return ()


class Customers:
    def __init__(self): self.calls = []
    def next_record_number(self): return 5500
    def create_customer_assisted(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return SimpleNamespace(customer_id=31, record_number=command.record_number)


class Model:
    def respond(self, message, *, available_tools):
        return ModelReply("Cadastro preparado.", (ToolRequest(
            "clientes.preparar_cadastro", {
                "name": "Maria da Silva", "phone": "71999999999",
                "address": "Rua A", "credit_limit": "500.00",
            }
        ),))


class CustomerAssistantTests(unittest.TestCase):
    def test_schema_e_rascunho_nao_persistem(self):
        PREPARE_CUSTOMER_REGISTRATION.schema.validate({
            "name": "Maria", "credit_limit": "10.00",
        })
        with self.assertRaises(ValueError):
            PREPARE_CUSTOMER_REGISTRATION.schema.validate({
                "name": "Maria", "credit_limit": 10.0,
            })
        customers = Customers()
        draft = CustomerRegistrationDraftService(customers).create(
            name="Maria", credit_limit="10.00"
        )
        self.assertEqual(draft.record_number, 5500)
        self.assertEqual(draft.credit_limit, Decimal("10.00"))
        self.assertEqual(customers.calls, [])

    def test_prepara_revisa_confirma_e_executa_uma_vez(self):
        customers = Customers()
        drafts = CustomerRegistrationDraftService(customers)
        assistant = create_draft_assistant(
            model=Model(), query_service=Queries(), security_service=Security(),
            audit_service=Audit(), session_id="sessao-real",
            customer_draft_service=drafts,
            customer_executor=NabiCodeCustomerRegistrationGateway(customers),
        )
        result = assistant.ask("Cadastre Maria").tool_results[0]
        self.assertTrue(result.success)
        self.assertFalse(result.payload["persisted"])
        self.assertEqual(result.payload["operation_kind"], "CUSTOMER_CREATE")
        challenge = assistant.review_draft(
            result.payload["draft_id"], result.payload["fingerprint"]
        )
        self.assertIs(
            challenge.required_capability,
            CapabilityLevel.REINFORCED_CONFIRMATION,
        )
        created, authorization = assistant.confirm_and_execute_customer(
            challenge.token, result.payload["draft_id"], result.payload["fingerprint"]
        )
        self.assertEqual(created.customer_id, 31)
        self.assertEqual(len(customers.calls), 1)
        self.assertEqual(customers.calls[0][1]["username"], "op")
        with self.assertRaises(PermissionError):
            authorization.consume(drafts.get(result.payload["draft_id"]), operation="CUSTOMER_CREATE")


if __name__ == "__main__": unittest.main()
