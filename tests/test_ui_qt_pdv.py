from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from commercial.application.dto import CustomerRecord, ProductRecord
from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.ports import PersistedCheckout
from commercial.domain.payments import PaymentMethod
from ui_qt.commercial.pdv_view_model import CheckoutInput, PDVViewModel

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
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
    other = CustomerRecord(8, "C8", "CLIENTE OITO", 88)
    final_consumer = CustomerRecord(1, "CONSUMIDOR_FINAL", "CONSUMIDOR FINAL", 0)

    def search(self, term, *, limit=30):
        if term == "varios":
            return (self.record, self.other)
        return (self.record,) if "sete" in str(term).casefold() else ()

    def get(self, customer_id):
        return {
            self.record.customer_id: self.record,
            self.other.customer_id: self.other,
            self.final_consumer.customer_id: self.final_consumer,
        }.get(customer_id)

    def get_final_consumer(self):
        return self.final_consumer


class FakeProducts:
    record = ProductRecord(9, "P9", "789", "PRODUTO NOVE", Decimal("10.00"))

    def search(self, term, *, limit=30):
        normalized = str(term).casefold()
        return (
            (self.record,)
            if any(token in normalized for token in ("p9", "789", "produto nove"))
            else ()
        )

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


class FakeCheckoutDialog:
    DialogCode = QDialog.DialogCode if QT_AVAILABLE else None
    result = QDialog.DialogCode.Rejected if QT_AVAILABLE else None
    exec_calls = 0

    def __init__(self, total, parent=None):
        self.total = total
        self.parent = parent

    def exec(self):
        type(self).exec_calls += 1
        return type(self).result

    def checkout_input(self):
        raise AssertionError("Diálogo cancelado não pode preparar checkout")


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

    def test_first_key_thousands_millions_backspace_and_delete_at_end(self):
        edit = MoneyEdit()
        edit.show()
        edit.setFocus()
        QTest.keyClicks(edit, "1000000")
        self.assertEqual(edit.text(), "1.000.000,00")
        self.assertEqual(edit.value(), Decimal("1000000.00"))
        QTest.keyClick(edit, Qt.Key.Key_Backspace)
        self.assertEqual(edit.text(), "100.000,00")
        QTest.keyClick(edit, Qt.Key.Key_Delete)
        self.assertEqual(edit.text(), "100.000,00")
        self.assertEqual(edit.cursorPosition(), len(edit.text()))

    def test_decimal_ctrl_a_and_replacement(self):
        edit = MoneyEdit()
        QTest.keyClicks(edit, "10,5")
        self.assertEqual(edit.text(), "10,50")
        QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(edit, "2000")
        self.assertEqual(edit.text(), "2.000,00")

    def test_partial_selection_delete_removes_only_selected_digits(self):
        edit = MoneyEdit()
        QTest.keyClicks(edit, "1234")
        edit.setSelection(2, 2)  # "23" em "1.234,00"
        QTest.keyClick(edit, Qt.Key.Key_Delete)
        self.assertEqual(edit.text(), "14,00")
        self.assertEqual(edit.value(), Decimal("14.00"))

        edit.set_value("1234")
        edit.setSelection(2, 2)
        QTest.keyClicks(edit, "9")
        self.assertEqual(edit.text(), "194,00")

    def test_ctrl_a_delete_and_ctrl_a_typing(self):
        edit = MoneyEdit()
        QTest.keyClicks(edit, "1234")
        QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(edit, Qt.Key.Key_Delete)
        self.assertEqual(edit.text(), "0,00")
        self.assertEqual(edit.value(), Decimal("0.00"))
        QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(edit, "9876")
        self.assertEqual(edit.text(), "9.876,00")

    def test_backspace_and_delete_with_cursor_in_middle(self):
        edit = MoneyEdit()
        QTest.keyClicks(edit, "1234")
        edit.setCursorPosition(2)  # após o ponto em "1.234,00"
        QTest.keyClick(edit, Qt.Key.Key_Backspace)
        self.assertEqual(edit.text(), "234,00")
        self.assertEqual(edit.cursorPosition(), 0)
        edit.setCursorPosition(1)
        QTest.keyClick(edit, Qt.Key.Key_Delete)
        self.assertEqual(edit.text(), "24,00")
        self.assertEqual(edit.cursorPosition(), 1)


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

    def _cart_with_customer(self):
        self._select_customer()
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()

    def test_window_opens_and_customer_id_is_source_of_truth(self):
        self.assertTrue(self.window.isVisible())
        self.assertIn("NABI VENDAS", self.window.windowTitle())
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

    def test_nabi_visual_hierarchy_and_shortcuts(self):
        self.assertEqual(self.window.cart.columnCount(), 4)
        self.assertEqual(
            [self.window.cart.horizontalHeaderItem(index).text() for index in range(4)],
            ["Produto / Serviço", "Qtd.", "Unitário", "Total"],
        )
        labels = [label.text() for label in self.window.findChildren(QLabel)]
        buttons = [button.text() for button in self.window.findChildren(QPushButton)]
        self.assertIn("▰  NABI VENDAS", labels)
        self.assertIn("ITENS DA VENDA", labels)
        self.assertIn("RESUMO DA VENDA", labels)
        self.assertIn("Vendas do dia  [F7]", buttons)
        self.assertIn("ORÇAMENTO DESLIGADO  [F5]", buttons)
        self.assertIn("FINALIZAR VENDA  [F9]", buttons)
        shortcuts = {shortcut.key().toString() for shortcut in self.window._shortcuts}
        self.assertEqual(shortcuts, {"Esc", "F9"})

    def test_empty_customer_enter_selects_final_consumer_and_advances(self):
        self.assertTrue(self.window.customer_search.hasFocus())
        QTest.keyClick(self.window.customer_search, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(self.view_model.session.customer_id, 1)
        self.assertEqual(self.view_model.selected_customer.code, "CONSUMIDOR_FINAL")
        self.assertIn("CONSUMIDOR FINAL", self.window.customer_selected.text())
        self.assertTrue(self.window.product_search.hasFocus())

    def test_empty_customer_enter_with_cart_focuses_checkout(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        self.window.customer_search.setFocus()
        QTest.keyClick(self.window.customer_search, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(self.view_model.session.customer_id, 1)
        self.assertTrue(self.window.checkout_button.hasFocus())

    def test_selected_customer_enter_preserves_real_id(self):
        self._select_customer()
        self.window.customer_search.setFocus()
        QTest.keyClick(self.window.customer_search, Qt.Key.Key_Return)
        self.assertEqual(self.view_model.session.customer_id, 7)
        self.assertTrue(self.window.product_search.hasFocus())

    def test_registered_customer_with_cart_focuses_checkout(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        self._select_customer()
        self.assertEqual(self.view_model.session.customer_id, 7)
        self.assertTrue(self.window.checkout_button.hasFocus())

    def test_customer_selected_before_item_focuses_active_item_input(self):
        self._select_customer()
        self.assertTrue(self.window.product_search.hasFocus())

        self.window._clear_customer()
        self.window.loose_item.setChecked(True)
        self.window.customer_search.setText("sete")
        self.window._select_customer(self.window.customer_results.item(0))
        self.assertTrue(self.window.description.hasFocus())

    def test_editing_selected_customer_text_invalidates_previous_id(self):
        self._select_customer()
        self.assertEqual(self.view_model.session.customer_id, 7)
        self.window.customer_search.setText("texto sem selecao")
        self.assertIsNone(self.view_model.selected_customer)
        self.assertIsNone(self.view_model.session.customer_id)

        self.window.customer_search.setFocus()
        QTest.keyClick(self.window.customer_search, Qt.Key.Key_Return)
        self.assertIsNone(self.view_model.selected_customer)
        self.assertIsNone(self.view_model.session.customer_id)
        self.assertTrue(self.window.customer_search.hasFocus())

    def test_ambiguous_customer_text_does_not_create_identity(self):
        self.window.customer_search.setText("varios")
        self.window.customer_search.setFocus()
        QTest.keyClick(self.window.customer_search, Qt.Key.Key_Return)
        self.assertIsNone(self.view_model.session.customer_id)
        self.assertIsNone(self.view_model.selected_customer)
        self.assertTrue(self.window.customer_search.hasFocus())

    def test_loose_item_enter_follows_description_quantity_price_then_adds(self):
        self.window.loose_item.setChecked(True)
        QTest.keyClicks(self.window.description, "Item pelo Enter")
        QTest.keyClick(self.window.description, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertTrue(self.window.quantity.hasFocus())
        self.window.quantity.setText("2")
        QTest.keyClick(self.window.quantity, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertTrue(self.window.price.hasFocus())
        self.window.price.set_value("12,50")
        QTest.keyClick(self.window.price, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(self.window.cart.rowCount(), 1)
        self.assertEqual(self.view_model.total, Decimal("25.00"))
        self.assertEqual(self.window.description.text(), "")
        self.assertEqual(self.window.quantity.text(), "1")
        self.assertEqual(self.window.price.value(), Decimal("0.00"))
        self.assertTrue(self.window.customer_search.hasFocus())

    def test_enter_never_adds_invalid_loose_item(self):
        self.window.loose_item.setChecked(True)
        QTest.keyClick(self.window.description, Qt.Key.Key_Return)
        self.assertEqual(self.window.cart.rowCount(), 0)
        self.assertTrue(self.window.description.hasFocus())

        QTest.keyClicks(self.window.description, "Item invalido")
        QTest.keyClick(self.window.description, Qt.Key.Key_Return)
        for invalid_quantity in ("0", "abc"):
            with self.subTest(quantity=invalid_quantity):
                self.window.quantity.setText(invalid_quantity)
                self.window.quantity.setFocus()
                QTest.keyClick(self.window.quantity, Qt.Key.Key_Return)
                self.assertEqual(self.window.cart.rowCount(), 0)
                self.assertTrue(self.window.quantity.hasFocus())

        self.window.quantity.setText("1")
        QTest.keyClick(self.window.quantity, Qt.Key.Key_Return)
        self.assertTrue(self.window.price.hasFocus())
        QTest.keyClick(self.window.price, Qt.Key.Key_Return)
        self.assertEqual(self.window.cart.rowCount(), 0)
        self.assertTrue(self.window.price.hasFocus())

    def test_registered_product_enter_follows_selection_quantity_price_and_adds(self):
        self.window.product_search.setText("P9")
        self.window.product_search.setFocus()
        QTest.keyClick(self.window.product_search, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(self.view_model.selected_product.product_id, 9)
        self.assertTrue(self.window.quantity.hasFocus())
        self.window.quantity.setText("3")
        QTest.keyClick(self.window.quantity, Qt.Key.Key_Return)
        self.assertTrue(self.window.price.hasFocus())
        QTest.keyClick(self.window.price, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(self.window.cart.rowCount(), 1)
        self.assertEqual(self.view_model.total, Decimal("30.00"))
        self.assertEqual(self.view_model.session.cart.items[0].product_id, 9)
        self.assertTrue(self.window.customer_search.hasFocus())

    def test_each_enter_performs_only_one_transition(self):
        self.window.product_search.setText("P9")
        self.window.product_search.setFocus()
        QTest.keyClick(self.window.product_search, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertTrue(self.window.quantity.hasFocus())
        self.assertEqual(self.window.cart.rowCount(), 0)

        QTest.keyClick(self.window.quantity, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertTrue(self.window.price.hasFocus())
        self.assertEqual(self.window.cart.rowCount(), 0)

        QTest.keyClick(self.window.price, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(self.window.cart.rowCount(), 1)

    def test_editing_selected_product_text_invalidates_previous_product(self):
        self.window.product_search.setText("P9")
        self.window.product_search.setFocus()
        QTest.keyClick(self.window.product_search, Qt.Key.Key_Return)
        self.assertEqual(self.view_model.selected_product.product_id, 9)

        self.window.product_search.setText("produto inexistente")
        self.assertIsNone(self.view_model.selected_product)
        self.assertEqual(self.window.price.value(), Decimal("0.00"))
        self.window.product_search.setFocus()
        QTest.keyClick(self.window.product_search, Qt.Key.Key_Return)
        self.assertIsNone(self.view_model.selected_product)
        self.assertEqual(self.window.cart.rowCount(), 0)
        self.assertTrue(self.window.product_search.hasFocus())

    def test_auto_repeat_enter_is_consumed_without_advancing(self):
        self.assertTrue(self.window.customer_search.hasFocus())
        event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier,
            "\r",
            True,
            2,
        )
        QApplication.sendEvent(self.window.customer_search, event)
        QApplication.processEvents()
        self.assertIsNone(self.view_model.selected_customer)
        self.assertIsNone(self.view_model.session.customer_id)
        self.assertTrue(self.window.customer_search.hasFocus())

    def test_normal_full_registered_product_flow_still_works(self):
        QTest.keyClick(self.window.customer_search, Qt.Key.Key_Return)
        self.window.product_search.setText("789")
        QTest.keyClick(self.window.product_search, Qt.Key.Key_Return)
        self.window.quantity.setText("2")
        QTest.keyClick(self.window.quantity, Qt.Key.Key_Return)
        QTest.keyClick(self.window.price, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(self.view_model.session.customer_id, 1)
        self.assertEqual(self.window.cart.rowCount(), 1)
        self.assertEqual(self.view_model.total, Decimal("20.00"))
        self.assertTrue(self.window.checkout_button.hasFocus())

    def test_item_included_with_customer_already_selected_focuses_checkout(self):
        self._select_customer()
        self.window.product_search.setText("P9")
        self.window.product_search.setFocus()
        QTest.keyClick(self.window.product_search, Qt.Key.Key_Return)
        QTest.keyClick(self.window.quantity, Qt.Key.Key_Return)
        QTest.keyClick(self.window.price, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(self.window.cart.rowCount(), 1)
        self.assertTrue(self.window.checkout_button.hasFocus())

    def test_multiple_registered_items_return_to_search_each_time(self):
        self._select_customer()
        for expected_rows in (1, 2, 3):
            self.window.product_search.setText("789")
            self.window.product_search.setFocus()
            QTest.keyClick(self.window.product_search, Qt.Key.Key_Enter)
            QTest.keyClick(self.window.quantity, Qt.Key.Key_Return)
            QTest.keyClick(self.window.price, Qt.Key.Key_Return)
            QApplication.processEvents()
            self.assertEqual(self.window.cart.rowCount(), expected_rows)
            self.assertTrue(self.window.checkout_button.hasFocus())
            self.window.product_search.setFocus()

    def test_enter_on_checkout_opens_dialog_once_without_persisting(self):
        self._cart_with_customer()
        FakeCheckoutDialog.exec_calls = 0
        with patch("ui_qt.commercial.pdv_window.CheckoutDialog", FakeCheckoutDialog):
            self.window.checkout_button.setFocus()
            QTest.keyClick(self.window.checkout_button, Qt.Key.Key_Return)
            QApplication.processEvents()
        self.assertEqual(FakeCheckoutDialog.exec_calls, 1)
        self.assertEqual(self.gateway.commands, [])
        self.assertTrue(self.window.checkout_button.hasFocus())

    def test_f9_opens_same_dialog(self):
        self._cart_with_customer()
        FakeCheckoutDialog.exec_calls = 0
        with patch("ui_qt.commercial.pdv_window.CheckoutDialog", FakeCheckoutDialog):
            QTest.keyClick(self.window, Qt.Key.Key_F9)
            QApplication.processEvents()
        self.assertEqual(FakeCheckoutDialog.exec_calls, 1)
        self.assertEqual(self.gateway.commands, [])

    def test_cancel_checkout_preserves_session_and_focus(self):
        self._cart_with_customer()
        original_items = self.view_model.session.cart.items
        original_total = self.view_model.total
        with patch("ui_qt.commercial.pdv_window.CheckoutDialog", FakeCheckoutDialog):
            self.window._checkout()
        self.assertEqual(self.view_model.session.cart.items, original_items)
        self.assertEqual(self.view_model.session.customer_id, 7)
        self.assertEqual(self.view_model.total, original_total)
        self.assertEqual(self.gateway.commands, [])
        self.assertTrue(self.window.checkout_button.hasFocus())

    def test_empty_cart_blocks_checkout_and_focuses_active_item(self):
        FakeCheckoutDialog.exec_calls = 0
        with patch("ui_qt.commercial.pdv_window.CheckoutDialog", FakeCheckoutDialog):
            self.window._checkout()
        self.assertEqual(FakeCheckoutDialog.exec_calls, 0)
        self.assertIn("Inclua ao menos um item", self.window.statusBar().currentMessage())
        self.assertTrue(self.window.product_search.hasFocus())

        self.window.loose_item.setChecked(True)
        with patch("ui_qt.commercial.pdv_window.CheckoutDialog", FakeCheckoutDialog):
            self.window._checkout()
        self.assertEqual(FakeCheckoutDialog.exec_calls, 0)
        self.assertTrue(self.window.description.hasFocus())

    def test_enter_does_not_invoke_checkout(self):
        calls = []
        self.window._checkout = lambda: calls.append("checkout")
        for widget in (self.window.customer_search, self.window.product_search):
            widget.setFocus()
            QTest.keyClick(widget, Qt.Key.Key_Return)
            QApplication.processEvents()
        self.assertEqual(calls, [])

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
