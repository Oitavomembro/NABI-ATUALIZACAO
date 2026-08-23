from __future__ import annotations

import os
import unittest
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from commercial.application.dto import CustomerRecord, ProductRecord
from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.ports import PersistedCheckout
from commercial.domain.payments import PaymentMethod
from ui_qt.commercial.pdv_view_model import CheckoutInput, PDVViewModel

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from ui_qt.commercial.pdv_window import PDVWindow
    from ui_qt.commercial.widgets.money_edit import MoneyEdit
except (ImportError, OSError) as qt_error:
    QT_AVAILABLE = False
    QT_UNAVAILABLE_REASON = str(qt_error)
else:
    QT_AVAILABLE = True
    QT_UNAVAILABLE_REASON = ""


class FakeCustomers:
    record = CustomerRecord(7, "C7", "CLIENTE SETE", 77)

    def search(self, term, *, limit=30):
        return (self.record,) if term else ()

    def get(self, customer_id):
        return self.record if customer_id == self.record.customer_id else None


class FakeProducts:
    record = ProductRecord(9, "P9", "789", "PRODUTO NOVE", Decimal("10.00"))

    def search(self, term, *, limit=30):
        return (self.record,) if term else ()

    def get(self, product_id):
        return self.record if product_id == self.record.product_id else None


class FakeCheckout:
    def __init__(self, error=None):
        self.error = error
        self.commands = []

    def checkout(self, command, *, customer, user):
        self.commands.append((command, customer, user))
        if self.error:
            raise self.error
        validation = command.payment_plan.validate_against(command.final_total)
        return PersistedCheckout(
            sale_id=41,
            total=command.final_total,
            received=validation.received,
            change=validation.change,
            payment_description="DINHEIRO",
            status="PAGO",
        )


def make_view_model(error=None):
    gateway = FakeCheckout(error)
    application = PDVApplicationService(
        customers=FakeCustomers(), products=FakeProducts(), checkout_gateway=gateway
    )
    return PDVViewModel(application), gateway


class PDVViewModelTests(unittest.TestCase):
    def _prepared(self, error=None):
        view_model, gateway = make_view_model(error)
        view_model.select_customer(7)
        view_model.add_loose_item("ITEM", "1", Decimal("100"))
        return view_model, gateway

    def test_approved_checkout_consumes_session_and_keeps_customer_id(self):
        view_model, gateway = self._prepared()
        result = view_model.checkout(
            CheckoutInput(PaymentMethod.CASH, Decimal("100")), user="Operador"
        )
        self.assertTrue(result.committed)
        self.assertTrue(view_model.session.cart.is_empty)
        self.assertEqual(gateway.commands[0][0].customer_id, 7)

    def test_refused_checkout_preserves_cart(self):
        view_model, _gateway = self._prepared(ValueError("Limite insuficiente"))
        result = view_model.checkout(
            CheckoutInput(PaymentMethod.CASH, Decimal("100")), user="Operador"
        )
        self.assertFalse(result.committed)
        self.assertIn("Limite", result.message)
        self.assertFalse(view_model.session.cart.is_empty)

    def test_entry_and_store_credit_schedule_are_delegated_to_application(self):
        view_model, gateway = self._prepared()
        result = view_model.checkout(
            CheckoutInput(
                PaymentMethod.STORE_CREDIT,
                Decimal("80"),
                entrance_method=PaymentMethod.PIX,
                entrance_amount=Decimal("20"),
                installment_count=3,
            ),
            user="Operador",
        )
        self.assertTrue(result.committed)
        command = gateway.commands[0][0]
        self.assertEqual(command.payment_plan.financed_value, Decimal("80.00"))
        self.assertEqual(command.credit_terms.installment_count, 3)


@unittest.skipUnless(QT_AVAILABLE, f"Runtime Qt indisponível: {QT_UNAVAILABLE_REASON}")
class MoneyEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_first_key_thousands_millions_backspace_and_delete(self):
        edit = MoneyEdit()
        edit.show()
        edit.setFocus()
        QTest.keyClicks(edit, "1000000")
        self.assertEqual(edit.text(), "1.000.000,00")
        self.assertEqual(edit.value(), Decimal("1000000.00"))
        QTest.keyClick(edit, Qt.Key.Key_Backspace)
        self.assertEqual(edit.text(), "100.000,00")
        QTest.keyClick(edit, Qt.Key.Key_Delete)
        self.assertEqual(edit.text(), "0,00")

    def test_decimal_ctrl_a_and_replacement(self):
        edit = MoneyEdit()
        QTest.keyClicks(edit, "10,5")
        self.assertEqual(edit.text(), "10,50")
        QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(edit, "2000")
        self.assertEqual(edit.text(), "2.000,00")


@unittest.skipUnless(QT_AVAILABLE, f"Runtime Qt indisponível: {QT_UNAVAILABLE_REASON}")
class PDVQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view_model, self.gateway = make_view_model()
        self.window = PDVWindow(self.view_model)
        self.window.show()
        QApplication.processEvents()

    def tearDown(self):
        self.window.close()

    def _select_customer(self):
        self.window.customer_search.setText("sete")
        item = self.window.customer_results.item(0)
        self.window._select_customer(item)

    def test_window_opens_and_customer_id_is_source_of_truth(self):
        self.assertTrue(self.window.isVisible())
        self._select_customer()
        self.assertEqual(self.view_model.session.customer_id, 7)
        self.assertIn("CLIENTE SETE", self.window.customer_selected.text())

    def test_loose_item_has_empty_field_first_key_and_updates_cart_total(self):
        self.window.loose_item.setChecked(True)
        QApplication.processEvents()
        self.assertEqual(self.window.description.placeholderText(), "")
        self.assertEqual(self.window.description.text(), "")
        self.assertTrue(self.window.description.hasFocus())
        QTest.keyClicks(self.window.description, "Caneta")
        self.assertEqual(self.window.description.text(), "Caneta")
        self.window.quantity.setText("2")
        self.window.price.set_value("10")
        self.window._add_item()
        self.assertEqual(self.window.cart.rowCount(), 1)
        self.assertEqual(self.view_model.total, Decimal("20.00"))
        self.assertIn("20,00", self.window.total_label.text())

    def test_registered_product_and_quantity(self):
        self.window.product_search.setText("P9")
        self.window._select_product(self.window.product_results.item(0))
        self.window.quantity.setText("3")
        self.window._add_item()
        self.assertEqual(self.view_model.total, Decimal("30.00"))
        self.assertEqual(self.view_model.session.cart.items[0].product_id, 9)

    def test_approved_checkout_consumes_session(self):
        self._select_customer()
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        result = self.view_model.checkout(
            CheckoutInput(PaymentMethod.CASH, Decimal("10")), user="Operador"
        )
        self.assertTrue(result.committed)
        self.assertTrue(result.session_consumed)
        self.assertTrue(self.view_model.session.cart.is_empty)
        self.assertEqual(self.gateway.commands[0][0].customer_id, 7)

    def test_refused_checkout_preserves_cart(self):
        view_model, _gateway = make_view_model(ValueError("Limite insuficiente"))
        view_model.select_customer(7)
        view_model.add_loose_item("ITEM", "1", Decimal("10"))
        result = view_model.checkout(
            CheckoutInput(PaymentMethod.CASH, Decimal("10")), user="Operador"
        )
        self.assertFalse(result.committed)
        self.assertIn("Limite", result.message)
        self.assertFalse(view_model.session.cart.is_empty)

    def test_store_credit_schedule_is_sent_through_application(self):
        self._select_customer()
        self.view_model.add_loose_item("ITEM", "1", Decimal("100"))
        result = self.view_model.checkout(
            CheckoutInput(
                PaymentMethod.STORE_CREDIT,
                Decimal("80"),
                entrance_method=PaymentMethod.PIX,
                entrance_amount=Decimal("20"),
                installment_count=3,
            ),
            user="Operador",
        )
        self.assertTrue(result.committed)
        command = self.gateway.commands[0][0]
        self.assertEqual(command.payment_plan.financed_value, Decimal("80.00"))
        self.assertEqual(command.credit_terms.installment_count, 3)


if __name__ == "__main__":
    unittest.main()
