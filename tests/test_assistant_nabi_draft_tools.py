from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from assistant_nabi import (
    AssistantActor, DraftToolRegistry, ModelReply, ToolRequest,
    create_draft_assistant,
)
from assistant_nabi.draft_tools import CREATE_SALE_DRAFT, CREATE_TARGET_SALE_DRAFT


class Security:
    session = SimpleNamespace(user=SimpleNamespace(username="op", profile="OPERADOR", active=True))
    def is_expired(self): return False
    def require(self, module, action): return (module, action) in {("produtos", "view"), ("clientes", "view"), ("vendas", "create")}


class Audit:
    def __init__(self): self.events = []
    def record_event(self, *args, **kwargs): self.events.append((args, kwargs))


class Queries:
    def search_products(self, term, *, limit): return ()
    def search_customers(self, term, *, limit): return ()
    def get_customer(self, customer_id): return None
    def get_product(self, product_id):
        return SimpleNamespace(product_id=product_id, code="P1", description="Café", unit_price=Decimal("10"), active=True)
    def product_stock(self, product_id):
        return SimpleNamespace(product_id=product_id, current_quantity=Decimal("20"), minimum_quantity=Decimal("0"), available=True, status="DISPONIVEL", allow_negative_stock=False)
    def high_stock_products(self, *, limit):
        return (SimpleNamespace(
            product_id=1, code="P1", description="Café",
            sale_price=Decimal("10"), current_stock=Decimal("20"),
            active=True, product_type="MERCADORIA",
        ),)


class Model:
    def respond(self, message, *, available_tools):
        return ModelReply("Preparei um rascunho.", (ToolRequest(
            "vendas.criar_rascunho",
            {"product_ids": [1], "quantities": ["2"], "payment_method": "PIX"},
        ),))


class DraftToolTests(unittest.TestCase):
    def test_schema_de_listas_e_fechado(self):
        CREATE_SALE_DRAFT.schema.validate({
            "product_ids": [1, 2], "quantities": ["1", "2.5"], "payment_method": "PIX"
        })
        for invalid in (
            {"product_ids": [], "quantities": ["1"], "payment_method": "PIX"},
            {"product_ids": [True], "quantities": ["1"], "payment_method": "PIX"},
            {"product_ids": [1], "quantities": [1.0], "payment_method": "PIX"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                CREATE_SALE_DRAFT.schema.validate(invalid)

    def test_assistente_cria_rascunho_sem_persistir(self):
        audit = Audit()
        service = create_draft_assistant(
            model=Model(), query_service=Queries(), security_service=Security(),
            audit_service=audit, session_id="sessao-real",
        )
        turn = service.ask("Monte dois cafés no PIX")
        self.assertFalse(turn.safe_failure)
        result = turn.tool_results[0]
        self.assertTrue(result.success)
        self.assertEqual(result.payload["total"], "20.00")
        self.assertFalse(result.payload["persisted"])
        self.assertTrue(result.payload["requires_confirmation"])
        self.assertEqual(len(audit.events), 1)
        challenge = service.review_draft(
            result.payload["draft_id"], result.payload["fingerprint"]
        )
        draft, authorization = service.confirm_draft(
            challenge.token, result.payload["draft_id"], result.payload["fingerprint"]
        )
        self.assertEqual(draft.fingerprint, authorization.fingerprint)
        with self.assertRaises(PermissionError):
            service.confirm_draft(
                challenge.token, result.payload["draft_id"], result.payload["fingerprint"]
            )

    def test_registry_fase2_recusa_mutacao(self):
        from assistant_nabi import CapabilityLevel, ToolDefinition, ToolKind
        registry = DraftToolRegistry(permissions=SimpleNamespace(allows=lambda *args: True), audit=SimpleNamespace(record=lambda **kwargs: None))
        with self.assertRaisesRegex(ValueError, "consultas e rascunhos"):
            registry.register(ToolDefinition("vendas.confirmar", ToolKind.MUTATION, CapabilityLevel.REINFORCED_CONFIRMATION, "vendas", "create"), SimpleNamespace(execute=lambda *args: {}))

    def test_ferramenta_por_valor_exige_politica_explicita_e_so_cria_rascunho(self):
        CREATE_TARGET_SALE_DRAFT.schema.validate({
            "target_amount": "50.00", "tolerance_amount": "0.00",
            "max_units_per_product": 5, "payment_method": "PIX",
        })
        class TargetModel:
            def respond(self, message, *, available_tools):
                return ModelReply("Sugestão pronta.", (ToolRequest(
                    "vendas.sugerir_rascunho_por_estoque",
                    {
                        "target_amount": "50.00", "tolerance_amount": "0.00",
                        "max_units_per_product": 5, "payment_method": "PIX",
                    },
                ),))
        service = create_draft_assistant(
            model=TargetModel(), query_service=Queries(), security_service=Security(),
            audit_service=Audit(), session_id="sessao-real",
        )
        result = service.ask("Monte cerca de 50 reais no PIX").tool_results[0]
        self.assertTrue(result.success)
        self.assertEqual(result.payload["total"], "50.00")
        self.assertEqual(
            result.payload["selection_policy"],
            "MAIOR_ESTOQUE_DENTRO_DA_TOLERANCIA",
        )
        self.assertFalse(result.payload["persisted"])


if __name__ == "__main__": unittest.main()
