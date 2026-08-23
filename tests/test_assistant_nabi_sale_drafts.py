from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from assistant_nabi import SaleDraftItemRequest, SaleDraftService


class Queries:
    def __init__(self):
        self.calls = []
        self.products = {
            1: SimpleNamespace(
                product_id=1, code="P1", description="Café", unit_price=Decimal("12.50"), active=True
            ),
            2: SimpleNamespace(
                product_id=2, code="P2", description="Leite", unit_price=Decimal("7.00"), active=True
            ),
            3: SimpleNamespace(
                product_id=3, code="P3", description="Inativo", unit_price=Decimal("9.00"), active=False
            ),
        }
        self.stocks = {
            1: SimpleNamespace(current_quantity=Decimal("10"), allow_negative_stock=False),
            2: SimpleNamespace(current_quantity=Decimal("2"), allow_negative_stock=True),
            3: SimpleNamespace(current_quantity=Decimal("5"), allow_negative_stock=False),
        }

    def get_product(self, product_id):
        self.calls.append(("product", product_id))
        return self.products.get(product_id)

    def product_stock(self, product_id):
        self.calls.append(("stock", product_id))
        return self.stocks[product_id]

    def get_customer(self, customer_id):
        self.calls.append(("customer", customer_id))
        return SimpleNamespace(customer_id=customer_id) if customer_id == 9 else None


class SaleDraftServiceTests(unittest.TestCase):
    def setUp(self):
        self.queries = Queries()
        self.service = SaleDraftService(self.queries)

    def test_cria_rascunho_imutavel_com_preco_e_estoque_oficiais(self):
        draft = self.service.create(
            (
                SaleDraftItemRequest(1, Decimal("2")),
                SaleDraftItemRequest(2, Decimal("3")),
            ),
            payment_method="pix",
        )
        self.assertEqual(draft.payment_method, "PIX")
        self.assertEqual(draft.total, Decimal("46.00"))
        self.assertEqual(draft.items[0].unit_price, Decimal("12.50"))
        self.assertEqual(draft.items[0].stock_after, Decimal("8.0000"))
        self.assertEqual(draft.items[1].stock_after, Decimal("-1.0000"))
        self.assertEqual(len(draft.fingerprint), 64)
        self.assertEqual(len(draft.draft_id), 32)
        self.assertEqual(
            self.queries.calls,
            [("product", 1), ("stock", 1), ("product", 2), ("stock", 2)],
        )

    def test_mesmo_conteudo_tem_mesmo_hash_mas_novo_identificador(self):
        request = (SaleDraftItemRequest(1, Decimal("1")),)
        first = self.service.create(request, payment_method="DINHEIRO")
        second = self.service.create(request, payment_method="DINHEIRO")
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.draft_id, second.draft_id)

    def test_estoque_insuficiente_falha_sem_qualquer_persistencia(self):
        with self.assertRaisesRegex(ValueError, "Estoque insuficiente"):
            self.service.create(
                (SaleDraftItemRequest(1, Decimal("11")),), payment_method="PIX"
            )
        self.assertFalse(hasattr(self.queries, "checkout"))

    def test_rejeita_produto_duplicado_inativo_e_float(self):
        with self.assertRaisesRegex(ValueError, "duas vezes"):
            self.service.create(
                (SaleDraftItemRequest(1, "1"), SaleDraftItemRequest(1, "2")),
                payment_method="PIX",
            )
        with self.assertRaisesRegex(ValueError, "inativo"):
            self.service.create(
                (SaleDraftItemRequest(3, "1"),), payment_method="PIX"
            )
        with self.assertRaisesRegex(ValueError, "texto decimal"):
            SaleDraftItemRequest(1, 1.5)

    def test_crediario_exige_cliente_real_e_cliente_inexistente_falha(self):
        with self.assertRaisesRegex(ValueError, "cliente identificado"):
            self.service.create(
                (SaleDraftItemRequest(1, "1"),), payment_method="CREDIARIO"
            )
        with self.assertRaisesRegex(ValueError, "Cliente não encontrado"):
            self.service.create(
                (SaleDraftItemRequest(1, "1"),), payment_method="PIX", customer_id=8
            )
        draft = self.service.create(
            (SaleDraftItemRequest(1, "1"),), payment_method="CREDIARIO", customer_id=9
        )
        self.assertEqual(draft.customer_id, 9)

    def test_hash_muda_quando_quantidade_pagamento_cliente_ou_preco_muda(self):
        base = self.service.create(
            (SaleDraftItemRequest(1, "1"),), payment_method="PIX"
        )
        quantity = self.service.create(
            (SaleDraftItemRequest(1, "2"),), payment_method="PIX"
        )
        payment = self.service.create(
            (SaleDraftItemRequest(1, "1"),), payment_method="DINHEIRO"
        )
        customer = self.service.create(
            (SaleDraftItemRequest(1, "1"),), payment_method="PIX", customer_id=9
        )
        self.queries.products[1].unit_price = Decimal("13.00")
        price = self.service.create(
            (SaleDraftItemRequest(1, "1"),), payment_method="PIX"
        )
        hashes = {
            base.fingerprint,
            quantity.fingerprint,
            payment.fingerprint,
            customer.fingerprint,
            price.fingerprint,
        }
        self.assertEqual(len(hashes), 5)


if __name__ == "__main__":
    unittest.main()
