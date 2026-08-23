from __future__ import annotations

from dataclasses import fields
from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from commercial.application.dto import CheckoutCommand, CheckoutResult, CustomerRecord, ProductRecord
from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.pdv_session import CheckoutState, PDVSession
from commercial.application.ports import PersistedCheckout, ProductLookupPort
from commercial.domain.payments import Payment, PaymentMethod


class FakeCustomers:
    def __init__(self):
        self.records = {
            1: CustomerRecord(1, "CONSUMIDOR_FINAL", "CONSUMIDOR FINAL", 0),
            7: CustomerRecord(7, "C7", "CLIENTE SETE", 70),
            8: CustomerRecord(8, "C8", "CLIENTE OITO", 80),
        }

    def search(self, term, *, limit=30):
        normalized = str(term).casefold()
        return tuple(
            item for item in self.records.values()
            if normalized in item.name.casefold() or normalized in item.code.casefold()
        )[:limit]

    def get(self, customer_id):
        return self.records.get(int(customer_id))

    def get_final_consumer(self):
        return self.records[1]


class FakeProducts:
    def __init__(self):
        self.records = {
            10: ProductRecord(10, "P10", "78910", "PRODUTO DEZ", Decimal("50.00")),
            11: ProductRecord(11, "P11", "78911", "INATIVO", Decimal("20.00"), False),
        }

    def search(self, term, *, limit=30):
        normalized = str(term).casefold()
        return tuple(
            item for item in self.records.values()
            if normalized in item.description.casefold()
            or normalized in item.code.casefold()
            or normalized in item.barcode.casefold()
        )[:limit]

    def get(self, product_id):
        return self.records.get(int(product_id))


class LookupOnlyProducts(FakeProducts):
    """Double que falha se o PDV tentar escrever em catálogo ou estoque."""

    def __init__(self):
        super().__init__()
        self.write_calls = []

    def create(self, *args, **kwargs):
        self.write_calls.append(("create", args, kwargs))
        raise AssertionError("O PDV não pode criar produtos.")

    def update(self, *args, **kwargs):
        self.write_calls.append(("update", args, kwargs))
        raise AssertionError("O PDV não pode editar produtos.")

    def delete(self, *args, **kwargs):
        self.write_calls.append(("delete", args, kwargs))
        raise AssertionError("O PDV não pode excluir produtos.")

    def move_stock(self, *args, **kwargs):
        self.write_calls.append(("move_stock", args, kwargs))
        raise AssertionError("Item avulso não pode movimentar estoque.")


class FakeCheckoutGateway:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def checkout(self, command, *, customer, user):
        self.calls.append((command, customer, user))
        if self.error is not None:
            raise self.error
        validation = command.payment_plan.validate_against(command.final_total)
        return PersistedCheckout(
            sale_id=91,
            total=command.final_total,
            received=validation.received,
            change=validation.change,
            payment_description=" + ".join(payment.method.value for payment in command.payment_plan.payments),
            status="PENDENTE" if command.payment_plan.has_store_credit else "PAGO",
        )


class FakeEvents:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.results = []

    def sale_committed(self, result):
        self.results.append(result)
        if self.fail:
            raise RuntimeError("falha técnica que não deve vazar")


def make_application(*, gateway=None, events=None):
    return PDVApplicationService(
        customers=FakeCustomers(),
        products=FakeProducts(),
        checkout_gateway=gateway or FakeCheckoutGateway(),
        events=events,
    )


def prepared_cash_session(application):
    session = application.new_session()
    application.select_customer(session, 7)
    application.add_product(session, 10, quantity=2)
    application.prepare_payments(
        session, [Payment(PaymentMethod.CASH, Decimal("100.00"))]
    )
    return session


class PDVApplicationSessionTests(unittest.TestCase):
    def test_fronteira_de_produtos_do_pdv_e_somente_consulta(self):
        public_operations = {
            name for name in ProductLookupPort.__dict__ if not name.startswith("_")
        }
        self.assertEqual(public_operations, {"search", "get"})
        self.assertFalse(
            public_operations & {"create", "update", "delete", "save", "stock"}
        )

    def test_item_avulso_nao_escreve_catalogo_nem_movimenta_estoque(self):
        products = LookupOnlyProducts()
        application = PDVApplicationService(
            customers=FakeCustomers(),
            products=products,
            checkout_gateway=FakeCheckoutGateway(),
        )
        session = application.new_session()

        loose = application.add_loose_item(
            session,
            description="SERVIÇO FORA DO CATÁLOGO",
            quantity="2",
            unit_price="15,00",
        )

        self.assertIsNone(loose.product_id)
        self.assertTrue(loose.is_loose)
        self.assertEqual(products.write_calls, [])

    def test_ajustes_por_valor_percentual_e_limites(self):
        app = make_application()
        self.assertEqual(
            app.resolve_adjustments(
                Decimal("100"), discount="10", surcharge="5"
            ),
            (Decimal("10.00"), Decimal("5.00"), Decimal("95.00")),
        )
        self.assertEqual(
            app.resolve_adjustments(
                Decimal("100"), discount="10", discount_type="PERCENT",
                surcharge="10", surcharge_type="PERCENT",
            ),
            (Decimal("10.00"), Decimal("9.00"), Decimal("99.00")),
        )
        with self.assertRaises(ValueError):
            app.resolve_adjustments(Decimal("100"), discount="101", discount_type="PERCENT")
        with self.assertRaises(ValueError):
            app.resolve_adjustments(Decimal("100"), discount="100")

    def test_configuracao_mista_valida_antes_de_mutar_sessao(self):
        app = make_application()
        session = app.new_session()
        app.add_product(session, 10, quantity=2)
        app.configure_checkout(
            session,
            payments=(Payment(PaymentMethod.PIX, "40"), Payment(PaymentMethod.CASH, "70")),
        )
        self.assertEqual(session.payment_plan.validate_against(session.total).change, Decimal("10.00"))

        clean = app.new_session()
        app.add_product(clean, 10, quantity=2)
        with self.assertRaises(ValueError):
            app.configure_checkout(clean, payments=(Payment(PaymentMethod.PIX, "99"),))
        self.assertIsNone(clean.payment_plan)
        self.assertEqual(clean.discount_amount, Decimal("0.00"))

    def test_consumidor_final_e_selecionado_por_id_real(self):
        application = make_application()
        session = application.new_session()
        customer = application.select_final_consumer(session)
        self.assertEqual(customer.code, "CONSUMIDOR_FINAL")
        self.assertEqual(session.customer_id, 1)

    def test_nova_sessao_e_cliente_inequivoco_por_id(self):
        application = make_application()
        session = application.new_session()
        self.assertIsInstance(session, PDVSession)
        self.assertEqual(session.checkout_state, CheckoutState.OPEN)
        self.assertTrue(session.cart.is_empty)
        customer = application.select_customer(session, 7)
        self.assertEqual(customer.customer_id, 7)
        self.assertEqual(session.customer_id, 7)
        application.clear_customer(session)
        self.assertIsNone(session.customer_id)

    def test_cliente_inexistente_nao_altera_sessao(self):
        application = make_application()
        session = application.new_session()
        with self.assertRaisesRegex(ValueError, "Cliente não encontrado"):
            application.select_customer(session, 999)
        self.assertIsNone(session.customer_id)

    def test_produto_cadastrado_item_avulso_e_carrinho(self):
        application = make_application()
        session = application.new_session()
        registered = application.add_product(session, 10, quantity=2)
        loose = application.add_loose_item(
            session,
            description="SERVIÇO LIVRE",
            quantity=1,
            unit_price="25,00",
        )
        self.assertEqual(registered.product_id, 10)
        self.assertIsNone(loose.product_id)
        self.assertEqual(session.total, Decimal("125.00"))
        application.change_quantity(session, loose.line_id, 2)
        self.assertEqual(session.total, Decimal("150.00"))
        application.change_unit_price(session, loose.line_id, "30,00", allowed=True)
        self.assertEqual(session.total, Decimal("160.00"))
        application.remove_item(session, loose.line_id)
        self.assertEqual(session.total, Decimal("100.00"))
        with self.assertRaises(ValueError):
            application.add_product(session, 11)

    def test_alteracao_do_carrinho_invalida_pagamento_preparado(self):
        application = make_application()
        session = prepared_cash_session(application)
        self.assertIsNotNone(session.payment_plan)
        application.change_quantity(session, session.cart.items[0].line_id, 1)
        self.assertIsNone(session.payment_plan)

    def test_edicao_de_item_invalida_pagamento_e_restringe_preco_cadastrado(self):
        application = make_application()
        session = prepared_cash_session(application)
        item = session.cart.items[0]
        with self.assertRaises(PermissionError):
            application.edit_item(
                session, item.line_id, quantity=1, unit_price="60",
                discount_percent=0,
            )
        self.assertIsNotNone(session.payment_plan)
        application.edit_item(
            session, item.line_id, quantity=1, unit_price="50",
            discount_percent=10,
        )
        self.assertIsNone(session.payment_plan)
        self.assertEqual(session.cart.items[0].subtotal, Decimal("45.00"))

    def test_preparacao_entrada_crediario_e_checkout_command(self):
        application = make_application()
        session = application.new_session()
        application.select_customer(session, 8)
        application.add_product(session, 10, quantity=10)
        terms = application.prepare_store_credit(
            session,
            entrance_payments=[Payment(PaymentMethod.PIX, Decimal("100.00"))],
            financed_value=Decimal("400.00"),
            due_dates=[date(2026, 9, 22), date(2026, 10, 22)],
        )
        command = application.prepare_checkout(session)
        self.assertEqual(command.customer_id, 8)
        self.assertEqual(command.payment_plan.financed_value, Decimal("400.00"))
        self.assertEqual(terms.down_payment, Decimal("100.00"))
        self.assertEqual(sum(item.amount for item in terms.installments), Decimal("400.00"))


class PDVApplicationCheckoutTests(unittest.TestCase):
    def test_consumidor_final_permite_venda_comum(self):
        gateway = FakeCheckoutGateway()
        application = make_application(gateway=gateway)
        session = application.new_session()
        application.select_final_consumer(session)
        application.add_product(session, 10)
        application.prepare_payments(
            session, [Payment(PaymentMethod.CASH, Decimal("50.00"))]
        )
        result = application.checkout(session, user="operador")
        self.assertTrue(result.committed)
        self.assertEqual(gateway.calls[0][0].customer_id, 1)
        self.assertEqual(gateway.calls[0][1].code, "CONSUMIDOR_FINAL")

    def test_checkout_aprovado_envia_customer_id_correto_e_consumo_sessao(self):
        gateway = FakeCheckoutGateway()
        application = make_application(gateway=gateway)
        session = prepared_cash_session(application)
        result = application.checkout(session, user="operador")

        self.assertTrue(result.success)
        self.assertTrue(result.committed)
        self.assertEqual(result.sale_id, 91)
        self.assertTrue(result.session_consumed)
        self.assertTrue(session.cart.is_empty)
        self.assertIsNone(session.customer_id)
        command, customer, user = gateway.calls[0]
        self.assertEqual(command.customer_id, 7)
        self.assertEqual(customer.customer_id, 7)
        self.assertEqual(user, "operador")
        self.assertEqual(result.receipt.customer.customer_id, 7)

    def test_checkout_recusado_pre_commit_preserva_sessao(self):
        gateway = FakeCheckoutGateway(error=ValueError("Limite de crédito insuficiente."))
        application = make_application(gateway=gateway)
        session = prepared_cash_session(application)
        original_items = session.cart.items
        result = application.checkout(session, user="operador")

        self.assertFalse(result.success)
        self.assertFalse(result.committed)
        self.assertFalse(result.session_consumed)
        self.assertIn("Limite de crédito", result.message)
        self.assertEqual(session.cart.items, original_items)
        self.assertEqual(session.customer_id, 7)
        self.assertEqual(session.checkout_state, CheckoutState.OPEN)

    def test_falha_tecnica_pre_commit_usa_mensagem_segura(self):
        application = make_application(
            gateway=FakeCheckoutGateway(error=RuntimeError("sqlite tabela interna segredo"))
        )
        session = prepared_cash_session(application)
        result = application.checkout(session, user="operador")
        self.assertFalse(result.committed)
        self.assertNotIn("sqlite", result.message.casefold())
        self.assertFalse(session.cart.is_empty)

    def test_falha_secundaria_pos_commit_mantem_sucesso_e_sessao_consumida(self):
        events = FakeEvents(fail=True)
        application = make_application(events=events)
        session = prepared_cash_session(application)
        result = application.checkout(session, user="operador")

        self.assertTrue(result.success)
        self.assertTrue(result.committed)
        self.assertTrue(result.secondary_effect_failed)
        self.assertTrue(result.session_consumed)
        self.assertTrue(session.cart.is_empty)
        self.assertIn("Não finalize novamente", result.message)
        self.assertNotIn("falha técnica", result.message)
        self.assertEqual(len(events.results), 1)

    def test_contratos_nao_possuem_campos_de_widget(self):
        forbidden = {"widget", "window", "entry", "label", "button", "cursor", "connection"}
        for contract in (CheckoutCommand, CheckoutResult, CustomerRecord, ProductRecord):
            names = {field.name.casefold() for field in fields(contract)}
            self.assertTrue(names.isdisjoint(forbidden))

        root = Path(__file__).resolve().parents[1] / "commercial"
        application_source = "\n".join(
            path.read_text(encoding="utf-8").casefold()
            for path in root.rglob("*.py")
        )
        for dependency in ("nabicode_legacy", "tkinter", "customtkinter", "pyside6", "openai"):
            self.assertNotIn(f"import {dependency}", application_source)
            self.assertNotIn(f"from {dependency}", application_source)


if __name__ == "__main__":
    unittest.main()
