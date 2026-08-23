from __future__ import annotations

import unittest
from copy import deepcopy
from decimal import Decimal

from assistant_nabi import PurchaseReceiptDraftService, PurchaseReceiptItemRequest
from assistant_nabi.purchase_gateway import NabiCodePurchaseAssistantGateway


class Gateway:
    def __init__(self):
        self.order = {
            "id": 7, "status": "ABERTO", "fornecedor_id": 3,
            "fornecedor_nome": "FORNECEDOR TESTE",
            "itens": [
                {"id": 11, "produto_id": 5, "codigo": "P5", "nome": "CAFÉ",
                 "quantidade_pendente": Decimal("10")},
                {"id": 12, "produto_id": 6, "codigo": "P6", "nome": "LEITE",
                 "quantidade_pendente": Decimal("2")},
            ],
        }
        self.mutations = 0

    def get_open_order(self, order_id):
        return deepcopy(self.order) if order_id == 7 else None


class PurchaseReceiptDraftTests(unittest.TestCase):
    def setUp(self):
        self.gateway = Gateway()
        self.service = PurchaseReceiptDraftService(self.gateway)

    def test_prepara_entrada_com_efeitos_deterministicos_sem_gravar(self):
        draft = self.service.create(7, (
            PurchaseReceiptItemRequest(11, "4", "8.50"),
            PurchaseReceiptItemRequest(12, "2", "5.00"),
        ), document="NF 123", generate_payable=True, due_date="2026-09-10")
        self.assertEqual(draft.total, Decimal("44.00"))
        self.assertEqual(draft.items[0].pending_after, Decimal("6.0000"))
        self.assertEqual(draft.items[1].pending_after, Decimal("0.0000"))
        self.assertEqual(len(draft.fingerprint), 64)
        self.assertEqual(self.gateway.mutations, 0)
        self.assertEqual(self.service.get(draft.draft_id), draft)

    def test_rejeita_item_alheio_excesso_duplicidade_float_e_financeiro_incompleto(self):
        invalid = (
            ((PurchaseReceiptItemRequest(99, "1", "1"),), "não pertence"),
            ((PurchaseReceiptItemRequest(12, "3", "1"),), "excede"),
            ((PurchaseReceiptItemRequest(11, "1", "1"), PurchaseReceiptItemRequest(11, "1", "1")), "mais de uma"),
        )
        for requests, message in invalid:
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                self.service.create(7, requests)
        with self.assertRaisesRegex(ValueError, "texto decimal"):
            PurchaseReceiptItemRequest(11, 1.0, "1")
        with self.assertRaisesRegex(ValueError, "vencimento"):
            self.service.create(7, (PurchaseReceiptItemRequest(11, "1", "1"),), generate_payable=True)

    def test_gateway_bloqueia_mutacao_ate_idempotencia_duravel(self):
        service = type("Purchase", (), {"repository": object()})()
        gateway = NabiCodePurchaseAssistantGateway(service)
        with self.assertRaisesRegex(PermissionError, "idempotência persistente"):
            gateway.receive()


if __name__ == "__main__":
    unittest.main()
