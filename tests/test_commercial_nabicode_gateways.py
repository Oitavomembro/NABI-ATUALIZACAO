from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import unittest

from commercial.application.dto import CheckoutCommand, CustomerRecord
from commercial.domain.cart import CartItem
from commercial.domain.credit import CreditTerms
from commercial.domain.payments import Payment, PaymentMethod, PaymentPlan
from commercial.infrastructure.checkout_gateway import NabiCodeCheckoutGateway
from commercial.infrastructure.customer_gateway import NabiCodeCustomerGateway
from commercial.infrastructure.product_gateway import NabiCodeProductGateway


class FakeDatabase:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def fetch_one(self, sql, parameters):
        self.calls.append((sql, parameters))
        return self.row


class FakeCustomerRepository:
    def __init__(self):
        self.database = FakeDatabase((7, "C7", "CLIENTE", 70, 500, 100))

    def search_sales_suggestions(self, term, *, limit):
        return [SimpleNamespace(id=7, codigo="C7", nome="CLIENTE", numero_ficha=70)]


class FakeProductService:
    def listar(self, term):
        return [{
            "id": 10, "codigo": "P10", "codigo_barras": "789",
            "nome": "PRODUTO", "preco_venda": Decimal("25.00"), "ativo": 1,
        }]

    def buscar(self, product_id):
        return self.listar("")[0] if int(product_id) == 10 else None


class FakeLegacyPDVService:
    def __init__(self):
        self.rates = []

    def ratear_total_itens(self, items, total):
        self.rates.append((items, total))
        adjusted = [dict(item) for item in items]
        adjusted[0]["preco"] = total
        adjusted[0]["subtotal"] = total
        return adjusted


class FakeTransactionService:
    def __init__(self):
        self.kwargs = None

    def finalize_sale(self, **kwargs):
        self.kwargs = kwargs
        total = sum(item["qtd"] * item["preco"] for item in kwargs["items"])
        return SimpleNamespace(
            sale_id=44,
            total=total,
            payment_description="PIX R$ 20.00 + CREDIARIO R$ 75.00",
            change=Decimal("0.00"),
            status="PENDENTE",
        )


class NabiCodeGatewayTests(unittest.TestCase):
    def test_checkout_gateway_preserva_autorizacao_pos(self):
        transaction = FakeTransactionService()
        gateway = NabiCodeCheckoutGateway(transaction, FakeLegacyPDVService())
        command = CheckoutCommand(
            customer_id=7,
            items=[CartItem("ITEM", 1, Decimal("100"))],
            payment_plan=PaymentPlan([
                Payment(PaymentMethod.CREDIT_CARD, Decimal("100"), "NSU123")
            ]),
        )
        gateway.checkout(command, customer=CustomerRecord(7, "C7", "CLIENTE"), user="op")
        payment = transaction.kwargs["payments"][0]
        self.assertEqual(payment["card_integration"], 2)
        self.assertEqual(payment["card_authorization"], "NSU123")

    def test_customer_gateway_pesquisa_e_obtem_por_id(self):
        repository = FakeCustomerRepository()
        gateway = NabiCodeCustomerGateway(repository)
        self.assertEqual(gateway.search("cli")[0].customer_id, 7)
        customer = gateway.get(7)
        self.assertEqual(customer.customer_id, 7)
        self.assertEqual(customer.credit_limit, Decimal("500"))
        self.assertEqual(repository.database.calls[0][1], (7,))

    def test_product_gateway_reutiliza_service(self):
        gateway = NabiCodeProductGateway(FakeProductService())
        self.assertEqual(gateway.search("produto")[0].product_id, 10)
        self.assertEqual(gateway.get(10).unit_price, Decimal("25.00"))
        self.assertIsNone(gateway.get(99))

    def test_checkout_gateway_traduz_item_avulso_ajustes_e_crediario(self):
        transaction = FakeTransactionService()
        pdv = FakeLegacyPDVService()
        gateway = NabiCodeCheckoutGateway(transaction, pdv)
        plan = PaymentPlan([
            Payment(PaymentMethod.PIX, Decimal("20.00")),
            Payment(PaymentMethod.STORE_CREDIT, Decimal("75.00")),
        ])
        terms = CreditTerms.create(
            down_payment=Decimal("20.00"),
            financed_value=Decimal("75.00"),
            due_dates=[date(2026, 9, 22), date(2026, 10, 22)],
        )
        command = CheckoutCommand(
            customer_id=7,
            items=[CartItem("ITEM LIVRE", 1, Decimal("100.00"))],
            payment_plan=plan,
            credit_terms=terms,
            discount_amount=Decimal("5.00"),
        )
        result = gateway.checkout(
            command,
            customer=CustomerRecord(7, "C7", "CLIENTE"),
            user="operador",
        )

        self.assertEqual(result.sale_id, 44)
        self.assertEqual(transaction.kwargs["customer_id"], 7)
        self.assertEqual(transaction.kwargs["customer_name"], "CLIENTE")
        self.assertIsNone(transaction.kwargs["items"][0]["produto_id"])
        self.assertTrue(transaction.kwargs["items"][0]["item_avulso"])
        credit = transaction.kwargs["payments"][1]
        self.assertEqual(credit["parcelas"], 2)
        self.assertEqual(credit["primeiro_vencimento"], "2026-09-22")
        self.assertEqual(transaction.kwargs["received"], Decimal("95.00"))
        self.assertEqual(pdv.rates[0][1], Decimal("95.00"))


if __name__ == "__main__":
    unittest.main()
