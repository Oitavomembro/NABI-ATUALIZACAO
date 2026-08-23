from __future__ import annotations

import unittest
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

from assistant_nabi import ModelReply, ToolRequest, create_draft_assistant
from assistant_nabi.purchase_drafts import PurchaseReceiptDraftService
from assistant_nabi.purchase_tools import PREPARE_PURCHASE_RECEIPT


class Security:
    session = SimpleNamespace(user=SimpleNamespace(username="op", profile="OPERADOR", active=True))
    def is_expired(self): return False
    def require(self, module, action): return (module, action) in {
        ("compras", "create"), ("produtos", "view"), ("clientes", "view"),
        ("vendas", "create"),
    }


class Audit:
    def __init__(self): self.events = []
    def record_event(self, *args, **kwargs): self.events.append((args, kwargs))


class CommercialQueries:
    def search_products(self, term, *, limit): return ()
    def search_customers(self, term, *, limit): return ()


class PurchaseGateway:
    def get_open_order(self, order_id):
        if order_id != 7: return None
        return deepcopy({
            "id": 7, "status": "ABERTO", "fornecedor_id": 3,
            "fornecedor_nome": "FORNECEDOR",
            "itens": [{
                "id": 11, "produto_id": 5, "codigo": "P5", "nome": "CAFÉ",
                "quantidade_pendente": Decimal("10"),
            }],
        })


class Model:
    def respond(self, message, *, available_tools):
        return ModelReply("Entrada preparada.", (ToolRequest(
            "compras.preparar_recebimento", {
                "order_id": 7, "order_item_ids": [11], "quantities": ["4"],
                "unit_costs": ["8.50"], "document": "NF 123",
                "generate_payable": True, "due_date": "2026-09-10",
            }
        ),))


class PurchaseToolTests(unittest.TestCase):
    def test_schema_fechado_e_listas_paralelas(self):
        PREPARE_PURCHASE_RECEIPT.schema.validate({
            "order_id": 7, "order_item_ids": [11], "quantities": ["1"],
            "unit_costs": ["8.50"],
        })
        with self.assertRaises(ValueError):
            PREPARE_PURCHASE_RECEIPT.schema.validate({
                "order_id": 7, "order_item_ids": [11], "quantities": [1.0],
                "unit_costs": ["8.50"],
            })

    def test_prepara_revisa_e_confirma_sem_executar_recebimento(self):
        audit = Audit()
        purchases = PurchaseReceiptDraftService(PurchaseGateway())
        assistant = create_draft_assistant(
            model=Model(), query_service=CommercialQueries(), security_service=Security(),
            audit_service=audit, session_id="sessao-real",
            purchase_draft_service=purchases,
        )
        result = assistant.ask("Prepare o recebimento").tool_results[0]
        self.assertTrue(result.success)
        self.assertEqual(result.payload["operation_kind"], "PURCHASE_RECEIPT")
        self.assertTrue(result.payload["execution_blocked"])
        self.assertFalse(result.payload["persisted"])
        challenge = assistant.review_draft(result.payload["draft_id"], result.payload["fingerprint"])
        draft, authorization = assistant.confirm_draft(
            challenge.token, result.payload["draft_id"], result.payload["fingerprint"]
        )
        self.assertEqual(draft.operation_kind, "PURCHASE_RECEIPT")
        self.assertEqual(authorization.fingerprint, draft.fingerprint)
        self.assertEqual(len(audit.events), 1)


if __name__ == "__main__": unittest.main()
