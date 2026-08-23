from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from assistant_nabi import SaleDraft, SaleDraftItem
from commercial.application.dto import CustomerRecord, ProductRecord
from commercial.application.pdv_session import PDVSession
from commercial.domain.cart import CartItem
from commercial.domain.payments import PaymentMethod
from ui_qt.commercial.pdv_view_model import PDVViewModel


class Application:
    def __init__(self):
        self.product = ProductRecord(1, "P1", "", "Café", Decimal("10"), True)
        self.final = CustomerRecord(1, "CONSUMIDOR_FINAL", "Consumidor Final")
        self.customer = CustomerRecord(9, "C9", "Maria")
        self.persisted = 0

    def new_session(self): return PDVSession()
    def get_product(self, product_id): return self.product if product_id == 1 else None
    def select_customer(self, session, customer_id):
        session.select_customer(customer_id); return self.customer
    def select_final_consumer(self, session):
        session.select_customer(self.final.customer_id); return self.final
    def add_product(self, session, product_id, *, quantity, discount_percent=0):
        session.add_item(CartItem(
            product_id=product_id, description="Café", quantity=quantity,
            unit_price=self.product.unit_price,
        ))


def draft(*, price=Decimal("10"), customer_id=None, payment="PIX"):
    item = SaleDraftItem(1, "P1", "Café", Decimal("2"), price, price * 2, Decimal("10"), Decimal("8"))
    return SaleDraft("d1", "a" * 64, customer_id, payment, (item,), price * 2)


class NabiDraftTransferTests(unittest.TestCase):
    def test_carrega_atomicamente_sem_checkout_e_sugere_pagamento(self):
        app = Application(); vm = PDVViewModel(app)
        vm.load_assistant_draft(draft())
        self.assertEqual(len(vm.session.cart.items), 1)
        self.assertEqual(vm.selected_customer.customer_id, 1)
        self.assertIs(vm.assistant_payment_method, PaymentMethod.PIX)
        self.assertEqual(app.persisted, 0)

    def test_recusa_substituir_carrinho_e_preco_alterado(self):
        app = Application(); vm = PDVViewModel(app)
        vm.load_assistant_draft(draft())
        with self.assertRaisesRegex(ValueError, "Esvazie ou suspenda"):
            vm.load_assistant_draft(draft())
        empty = PDVViewModel(app)
        with self.assertRaisesRegex(ValueError, "mudou"):
            empty.load_assistant_draft(draft(price=Decimal("11")))
        self.assertTrue(empty.session.cart.is_empty)


if __name__ == "__main__": unittest.main()
