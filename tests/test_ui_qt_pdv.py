from __future__ import annotations

import os
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from commercial.application.dto import (
    BudgetDocument, CustomerRecord, ProductRecord, SuspendedSale,
)
from commercial.application.pdv_application_service import PDVApplicationService
from commercial.application.ports import PersistedCheckout
from commercial.domain.cart import CartItem
from commercial.domain.payments import Payment, PaymentMethod
from ui_qt.commercial.pdv_view_model import CheckoutInput, PDVViewModel

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPushButton
    from ui_qt.commercial.checkout_dialog import CheckoutDialog
    from ui_qt.commercial.cart_item_dialog import CartItemDialog
    from ui_qt.commercial.budget_dialog import BudgetListDialog, BudgetPreviewDialog
    from ui_qt.commercial.suspended_sale_dialog import SuspendedSaleListDialog
    from ui_qt.commercial.pdv_window import PDVWindow
    from ui_qt.commercial.post_sale_dialog import PostSaleDialog
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


class FakeBudgets:
    def __init__(self):
        self.open = []
        self.output_calls = []

    def save(self, *, customer_id, customer_name, items):
        budget = BudgetDocument(
            budget_id=f"B{len(self.open) + 1}",
            created_at="2026-08-23T12:00:00",
            customer_id=customer_id,
            customer_name=customer_name,
            items=items,
            total=sum(item.subtotal for item in items),
        )
        self.open.append(budget)
        return budget

    def list_open(self):
        return tuple(self.open)

    def consume(self, budget_id):
        budget = next(item for item in self.open if item.budget_id == budget_id)
        self.open.remove(budget)
        return budget

    def preview_text(self, budget):
        self.output_calls.append(("preview", budget.budget_id))
        return "ORÇAMENTO — SEM VALOR FISCAL\nTOTAL"

    def print_thermal(self, budget):
        self.output_calls.append(("print", budget.budget_id))
        return "IMPRESSORA"

    def generate_pdf(self, budget):
        self.output_calls.append(("pdf", budget.budget_id))
        return "C:/teste/orcamento.pdf"

    def open_file(self, path):
        self.output_calls.append(("open", path))
        return path


class FakeSuspendedSales:
    def __init__(self):
        self.open = []

    def suspend(self, *, customer_id, customer_name, items):
        suspended = SuspendedSale(
            suspended_id=f"S{len(self.open) + 1}",
            created_at="2026-08-23T15:00:00",
            customer_id=customer_id,
            customer_name=customer_name,
            items=items,
            total=sum(item.subtotal for item in items),
        )
        self.open.append(suspended)
        return suspended

    def list_open(self):
        return tuple(self.open)

    def resume(self, suspended_id):
        suspended = next(
            item for item in self.open if item.suspended_id == suspended_id
        )
        self.open.remove(suspended)
        return suspended


def make_view_model(
    error=None, receipt_output=None, budgets=None, suspended_sales=None
):
    gateway = FakeCheckout(error)
    budgets = budgets or FakeBudgets()
    suspended_sales = suspended_sales or FakeSuspendedSales()
    application = PDVApplicationService(
        customers=FakeCustomers(), products=FakeProducts(), checkout_gateway=gateway,
        receipt_output=receipt_output,
        budgets=budgets, budget_output=budgets,
        suspended_sales=suspended_sales,
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


class FakeAcceptedCheckoutDialog:
    DialogCode = QDialog.DialogCode if QT_AVAILABLE else None

    def __init__(self, _view_model, parent=None):
        self.parent = parent

    def exec(self):
        return self.DialogCode.Accepted

    def checkout_input(self):
        return CheckoutInput(PaymentMethod.CASH, Decimal("10.00"))


class FakePostSaleDialog:
    calls = []

    def __init__(self, _view_model, result, parent=None):
        type(self).calls.append(("init", result.sale_id, parent))

    def exec(self):
        type(self).calls.append(("exec",))
        return QDialog.DialogCode.Accepted


class FakeBudgetPreviewDialog:
    calls = []

    def __init__(self, _view_model, budget, parent=None):
        type(self).calls.append(("init", budget.budget_id, parent))

    def exec(self):
        type(self).calls.append(("exec",))
        return QDialog.DialogCode.Accepted


class FakeBudgetListDialog:
    selected_budget_id = None

    def __init__(self, _view_model, budgets, parent=None):
        self.budgets = budgets
        self.parent = parent
        self.selected_budget_id = type(self).selected_budget_id

    def exec(self):
        return QDialog.DialogCode.Accepted


class FakeSuspendedSaleListDialog:
    selected_suspended_id = None

    def __init__(self, suspended_sales, parent=None):
        self.suspended_sales = suspended_sales
        self.parent = parent
        self.selected_suspended_id = type(self).selected_suspended_id

    def exec(self):
        return QDialog.DialogCode.Accepted


class FakeCartItemDialog:
    DialogCode = QDialog.DialogCode if QT_AVAILABLE else None
    quantity_value = "2"
    price_value = Decimal("15.00")
    discount_value = Decimal("10.00")

    class TextField:
        def text(self):
            return FakeCartItemDialog.quantity_value

    class MoneyField:
        def __init__(self, attribute):
            self.attribute = attribute

        def value(self):
            return getattr(FakeCartItemDialog, self.attribute)

    def __init__(self, item, parent=None):
        self.item = item
        self.parent = parent
        self.quantity = self.TextField()
        self.price = self.MoneyField("price_value")
        self.discount = self.MoneyField("discount_value")

    def exec(self):
        return self.DialogCode.Accepted


class FakeCancelledCartItemDialog(FakeCartItemDialog):
    def exec(self):
        return self.DialogCode.Rejected


class FakeReceiptOutput:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def print_thermal(self, receipt):
        self.calls.append(("print", receipt.sale_id))
        if self.error:
            raise self.error
        return "IMPRESSORA TESTE"

    def generate_pdf(self, receipt):
        self.calls.append(("pdf", receipt.sale_id))
        if self.error:
            raise self.error
        return "C:/teste/comprovante.pdf"

    def open_file(self, path):
        self.calls.append(("open", path))
        return path


class PDVViewModelTests(unittest.TestCase):
    def test_comprovante_recusa_resultado_sem_commit(self):
        output = FakeReceiptOutput()
        view_model, _gateway = make_view_model(
            error=ValueError("venda recusada"), receipt_output=output
        )
        view_model.select_customer(7)
        view_model.add_loose_item("ITEM", "1", Decimal("100"))
        result = view_model.checkout(
            CheckoutInput(PaymentMethod.CASH, Decimal("100")), user="Operador"
        )
        self.assertFalse(result.committed)
        with self.assertRaisesRegex(ValueError, "venda confirmada"):
            view_model.application.print_receipt(result)
        with self.assertRaisesRegex(ValueError, "venda confirmada"):
            view_model.application.generate_receipt_pdf(result)
        self.assertEqual(output.calls, [])

    def test_checkout_confirmado_nao_pode_ser_repetido(self):
        view_model, gateway = self._prepared()
        data = CheckoutInput(PaymentMethod.CASH, Decimal("100"))
        self.assertTrue(view_model.checkout(data, user="Operador").committed)
        with self.assertRaises(ValueError):
            view_model.checkout(data, user="Operador")
        self.assertEqual(len(gateway.commands), 1)

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
class CheckoutDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view_model, self.gateway = make_view_model()
        self.view_model.select_customer(7)
        self.view_model.add_loose_item("ITEM", "1", Decimal("100"))
        self.dialog = CheckoutDialog(self.view_model)
        self.dialog.show()
        QApplication.processEvents()

    def tearDown(self):
        self.dialog.close()

    def test_formas_valor_inicial_e_dinheiro_exato(self):
        methods = {
            self.dialog.method.itemData(index)
            for index in range(self.dialog.method.count())
        }
        self.assertEqual(methods, set(PaymentMethod))
        self.assertEqual(self.dialog.amount.value(), Decimal("100.00"))
        preview = self.view_model.preview_checkout(self.dialog._candidate_input())
        self.assertEqual(preview[1].change, Decimal("0.00"))

    def test_enter_no_botao_adiciona_exatamente_um_pagamento(self):
        self.dialog.add_payment.setFocus()
        QTest.keyClick(self.dialog.add_payment, Qt.Key.Key_Return)
        QApplication.processEvents()
        self.assertEqual(len(self.dialog._payments), 1)
        self.assertEqual(self.dialog._payments[0].amount, Decimal("100.00"))
        self.assertTrue(self.dialog.discount_type.hasFocus())

    def test_enter_repetido_apos_total_coberto_nao_duplica_pagamento(self):
        self.dialog.add_payment.setFocus()
        QTest.keyClick(self.dialog.add_payment, Qt.Key.Key_Return)
        self.assertEqual(len(self.dialog._payments), 1)
        self.assertTrue(self.dialog.discount_type.hasFocus())
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
        self.assertEqual(len(self.dialog._payments), 1)

    def test_total_coberto_bloqueia_nova_inclusao_ate_por_clique(self):
        self.assertTrue(self.dialog._add_payment())
        self.assertFalse(self.dialog._add_payment())
        self.assertEqual(len(self.dialog._payments), 1)
        self.assertIn("já está coberto", self.dialog.error_label.text())

    def test_pagamento_parcial_prepara_saldo_restante_e_mantem_fluxo_misto(self):
        self.dialog.amount.set_value("40")
        self.assertTrue(self.dialog._add_payment())
        self.assertEqual(self.dialog.amount.value(), Decimal("60.00"))
        self.assertTrue(self.dialog.method.hasFocus())

    def test_rotulo_de_troco_e_grande_e_nao_diz_potencial(self):
        self.dialog.amount.set_value("120")
        self.dialog._refresh_totals()
        self.assertEqual(self.dialog.balance_label.text(), "TROCO: R$ 20,00")
        self.assertNotIn("potencial", self.dialog.balance_label.text().casefold())
        self.assertIn("font-size: 28px", self.dialog.balance_label.styleSheet())

    def test_auto_repeat_no_botao_nao_adiciona_pagamento(self):
        self.dialog.add_payment.setFocus()
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier, "\r", True, 2,
        )
        QApplication.sendEvent(self.dialog.add_payment, event)
        QApplication.processEvents()
        self.assertEqual(self.dialog._payments, [])
        self.assertTrue(self.dialog.add_payment.hasFocus())

    def test_shift_enter_no_botao_nao_adiciona_e_volta_ao_campo_anterior(self):
        self.dialog.add_payment.setFocus()
        QTest.keyClick(
            self.dialog.add_payment,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
        )
        QApplication.processEvents()
        self.assertEqual(self.dialog._payments, [])
        self.assertTrue(self.dialog.amount.hasFocus())

    def test_shift_enter_auto_repeat_no_botao_e_consumido_sem_adicionar(self):
        self.dialog.add_payment.setFocus()
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier, "\r", True, 2,
        )
        QApplication.sendEvent(self.dialog.add_payment, event)
        QApplication.processEvents()
        self.assertEqual(self.dialog._payments, [])
        self.assertTrue(self.dialog.add_payment.hasFocus())

    def test_erro_ao_adicionar_mantem_foco_no_valor(self):
        self.dialog.amount.clear_value()
        self.dialog.add_payment.setFocus()
        QTest.keyClick(self.dialog.add_payment, Qt.Key.Key_Return)
        self.assertEqual(self.dialog._payments, [])
        self.assertTrue(self.dialog.amount.hasFocus())

    def test_pagamento_misto_inteiro_pode_ser_montado_pelo_teclado(self):
        self.dialog.method.setFocus()
        QTest.keyClick(self.dialog.method, Qt.Key.Key_Down)  # PIX
        QTest.keyClick(self.dialog.method, Qt.Key.Key_Return)
        self.dialog.amount.set_value("40")
        QTest.keyClick(self.dialog.amount, Qt.Key.Key_Return)
        self.assertTrue(self.dialog.add_payment.hasFocus())
        QTest.keyClick(self.dialog.add_payment, Qt.Key.Key_Return)

        QTest.keyClick(self.dialog.method, Qt.Key.Key_Home)  # DINHEIRO
        QTest.keyClick(self.dialog.method, Qt.Key.Key_Return)
        self.dialog.amount.set_value("60")
        QTest.keyClick(self.dialog.amount, Qt.Key.Key_Return)
        QTest.keyClick(self.dialog.add_payment, Qt.Key.Key_Return)
        self.assertEqual(
            tuple(payment.method for payment in self.dialog._payments),
            (PaymentMethod.PIX, PaymentMethod.CASH),
        )
        preview = self.view_model.preview_checkout(self.dialog._candidate_input())
        self.assertEqual(preview[1].received, Decimal("100.00"))

    def test_dinheiro_acima_gera_troco_e_pix_insuficiente_bloqueia(self):
        self.dialog.amount.set_value("120")
        preview = self.view_model.preview_checkout(self.dialog._candidate_input())
        self.assertEqual(preview[1].change, Decimal("20.00"))
        self.dialog.method.setCurrentIndex(self.dialog.method.findData(PaymentMethod.PIX))
        self.dialog.amount.set_value("99")
        with self.assertRaisesRegex(ValueError, "não atingem"):
            self.view_model.preview_checkout(self.dialog._candidate_input())

    def test_cartoes_autorizacao_opcional_e_pagamento_misto(self):
        self.dialog._payments = (
            [Payment(PaymentMethod.DEBIT, "30"),
             Payment(PaymentMethod.CREDIT_CARD, "30", "NSU1"),
             Payment(PaymentMethod.OTHER, "10"),
             Payment(PaymentMethod.CASH, "30")]
        )
        preview = self.view_model.preview_checkout(self.dialog._candidate_input())
        self.assertEqual(preview[1].received, Decimal("100.00"))

    def test_trocar_credito_por_pix_limpa_autorizacao_oculta(self):
        self.dialog.method.setCurrentIndex(
            self.dialog.method.findData(PaymentMethod.CREDIT_CARD)
        )
        self.dialog.authorization.setText("NSU-ANTIGO")
        self.dialog.method.setCurrentIndex(self.dialog.method.findData(PaymentMethod.PIX))
        self.assertEqual(self.dialog.authorization.text(), "")
        self.assertFalse(self.dialog.authorization.isVisible())

        payment = self.dialog._current_payment()
        self.assertEqual(payment.method, PaymentMethod.PIX)
        self.assertEqual(payment.card_authorization, "")
        self.assertEqual(
            self.view_model.preview_checkout(self.dialog._candidate_input())[1].change,
            Decimal("0.00"),
        )
        self.dialog.method.setCurrentIndex(
            self.dialog.method.findData(PaymentMethod.CREDIT_CARD)
        )
        self.assertEqual(self.dialog.authorization.text(), "")

    def test_ajustes_percentuais_recalculam_total(self):
        self.dialog.discount_type.setCurrentIndex(1)
        self.dialog.discount.set_value("10")
        self.dialog.surcharge_type.setCurrentIndex(1)
        self.dialog.surcharge.set_value("10")
        self.dialog.amount.set_value("99")
        preview = self.view_model.preview_checkout(self.dialog._candidate_input())
        self.assertEqual(preview[-1], Decimal("99.00"))

    def test_crediario_sem_entrada_e_com_entrada(self):
        due = date(2026, 9, 22)
        no_entry = CheckoutInput(
            payments=(Payment(PaymentMethod.STORE_CREDIT, "100"),),
            installment_count=2, first_due_date=due,
        )
        self.assertEqual(self.view_model.preview_checkout(no_entry)[2].installment_count, 2)
        with_entry = CheckoutInput(
            payments=(Payment(PaymentMethod.PIX, "20"), Payment(PaymentMethod.STORE_CREDIT, "80")),
            installment_count=3, first_due_date=due,
        )
        preview = self.view_model.preview_checkout(with_entry)
        self.assertEqual(preview[2].down_payment, Decimal("20.00"))

    def test_enter_shift_enter_e_auto_repeat(self):
        self.dialog.method.setFocus()
        QTest.keyClick(self.dialog.method, Qt.Key.Key_Return)
        self.assertTrue(self.dialog.amount.hasFocus())
        QTest.keyClick(
            self.dialog.amount, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertTrue(self.dialog.method.hasFocus())
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier, "\r", True, 2,
        )
        QApplication.sendEvent(self.dialog.method, event)
        self.assertTrue(self.dialog.method.hasFocus())

    def test_revisao_e_confirmacao_sao_acoes_separadas(self):
        with patch.object(QMessageBox, "information") as information:
            self.dialog._review()
        self.assertEqual(information.call_count, 1)
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)
        self.assertTrue(self.dialog.confirm_button.isEnabled())
        self.assertEqual(self.gateway.commands, [])

        self.dialog._confirm()
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNotNone(self.dialog.checkout_input())
        self.assertEqual(self.gateway.commands, [])

    def test_confirmar_sem_revisao_valida_e_impossivel(self):
        self.dialog._confirm()
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)
        self.assertIsNone(self.dialog._confirmed_input)
        self.assertIn("Revise", self.dialog.error_label.text())

    def test_alteracao_posterior_invalida_revisao(self):
        with patch.object(QMessageBox, "information"):
            self.dialog._review()
        self.assertTrue(self.dialog.confirm_button.isEnabled())

        self.dialog.discount.set_value("1")

        self.assertIsNone(self.dialog._reviewed_input)
        self.assertFalse(self.dialog.confirm_button.isEnabled())
        self.dialog._confirm()
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)

    def test_dupla_confirmacao_nao_produz_duas_acoes(self):
        with patch.object(QMessageBox, "information"):
            self.dialog._review()
        with patch.object(self.dialog, "accept", wraps=self.dialog.accept) as accept:
            self.dialog._confirm()
            self.dialog._confirm()
        self.assertEqual(accept.call_count, 1)


@unittest.skipUnless(QT_AVAILABLE, f"Runtime Qt indisponível: {QT_UNAVAILABLE_REASON}")
class PostSaleDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def _dialog(self, *, error=None):
        output = FakeReceiptOutput(error)
        view_model, _gateway = make_view_model(receipt_output=output)
        view_model.select_customer(7)
        view_model.add_loose_item("ITEM", "1", Decimal("100"))
        result = view_model.checkout(
            CheckoutInput(PaymentMethod.CASH, Decimal("100")), user="Operador"
        )
        return PostSaleDialog(view_model, result), output

    def test_abrir_ou_cancelar_pos_venda_nao_emite_comprovante(self):
        dialog, output = self._dialog()
        self.assertEqual(output.calls, [])
        dialog.reject()
        self.assertEqual(output.calls, [])

    def test_impresso_e_pdf_exigem_acoes_explicitas(self):
        dialog, output = self._dialog()
        with patch.object(QMessageBox, "information"):
            dialog._print()
        self.assertEqual(output.calls, [("print", 41)])

        dialog, output = self._dialog()
        dialog._pdf()
        self.assertEqual(
            output.calls,
            [("pdf", 41), ("open", "C:/teste/comprovante.pdf")],
        )

    def test_falha_de_saida_nao_repete_venda_e_mantem_dialogo(self):
        dialog, output = self._dialog(error=RuntimeError("falha de impressão"))
        with patch.object(QMessageBox, "critical") as critical:
            dialog._print()
        self.assertEqual(critical.call_count, 1)
        self.assertEqual(output.calls, [("print", 41)])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)


@unittest.skipUnless(QT_AVAILABLE, f"Runtime Qt indisponível: {QT_UNAVAILABLE_REASON}")
class BudgetDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view_model, _gateway = make_view_model()
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.budget = self.view_model.save_budget()

    def test_abrir_e_fechar_previa_nao_imprime_nem_persiste_venda(self):
        output = self.view_model.application.budget_output
        dialog = BudgetPreviewDialog(self.view_model, self.budget)
        self.assertEqual(output.output_calls, [("preview", "B1")])
        dialog.reject()
        self.assertEqual(output.output_calls, [("preview", "B1")])

    def test_enter_shift_enter_e_auto_repeat_na_previa(self):
        output = self.view_model.application.budget_output
        dialog = BudgetPreviewDialog(self.view_model, self.budget)
        dialog.show()
        dialog.print_button.setFocus()
        QTest.keyClick(dialog.print_button, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.assertNotIn(("print", "B1"), output.output_calls)
        repeat = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier,
            "", True, 2,
        )
        QApplication.sendEvent(dialog.print_button, repeat)
        self.assertNotIn(("print", "B1"), output.output_calls)
        dialog.print_button.setFocus()
        with patch.object(QMessageBox, "information"):
            QTest.keyClick(dialog.print_button, Qt.Key.Key_Return)
        self.assertEqual(output.output_calls.count(("print", "B1")), 1)
        dialog.close()

    def test_esc_fecha_somente_previa_e_preserva_janela_pdv(self):
        window = PDVWindow(self.view_model)
        window.show()
        dialog = BudgetPreviewDialog(self.view_model, self.budget, window)
        dialog.show()
        QApplication.processEvents()
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        QApplication.processEvents()
        self.assertFalse(dialog.isVisible())
        self.assertTrue(window.isVisible())
        window.close()

    def test_editor_de_item_tem_fluxo_deterministico_e_bloqueia_auto_repeat(self):
        item = self.budget.items[0]
        dialog = CartItemDialog(item)
        dialog.show()
        QApplication.processEvents()
        self.assertTrue(dialog.quantity.hasFocus())
        repeat = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier, "", True, 2,
        )
        QApplication.sendEvent(dialog.quantity, repeat)
        self.assertTrue(dialog.quantity.hasFocus())
        QTest.keyClick(dialog.quantity, Qt.Key.Key_Return)
        self.assertTrue(dialog.price.hasFocus())
        QTest.keyClick(dialog.price, Qt.Key.Key_Return)
        self.assertTrue(dialog.discount.hasFocus())
        QTest.keyClick(dialog.discount, Qt.Key.Key_Return)
        self.assertTrue(dialog.apply_button.hasFocus())
        dialog.close()

    def test_lista_real_enter_visualiza_uma_vez_sem_consumir_orcamento(self):
        dialog = BudgetListDialog(self.view_model, (self.budget,))
        dialog.show()
        QApplication.processEvents()
        with patch("ui_qt.commercial.budget_dialog.BudgetPreviewDialog") as preview:
            preview.return_value.exec.return_value = QDialog.DialogCode.Rejected
            QTest.keyClick(dialog.table, Qt.Key.Key_Return)
            self.assertEqual(preview.call_count, 1)
            repeat = QKeyEvent(
                QEvent.Type.KeyPress, Qt.Key.Key_Return,
                Qt.KeyboardModifier.NoModifier, "", True, 2,
            )
            QApplication.sendEvent(dialog.table, repeat)
            self.assertEqual(preview.call_count, 1)
        self.assertIsNone(dialog.selected_budget_id)
        self.assertEqual(len(self.view_model.application.budgets.open), 1)
        dialog.close()

    def test_lista_real_shift_enter_volta_sem_carregar(self):
        dialog = BudgetListDialog(self.view_model, (self.budget,))
        dialog.show()
        dialog.preview_button.setFocus()
        QTest.keyClick(
            dialog.preview_button, Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
        )
        self.assertIsNone(dialog.selected_budget_id)
        self.assertEqual(len(self.view_model.application.budgets.open), 1)
        self.assertFalse(dialog.preview_button.hasFocus())
        dialog.close()


@unittest.skipUnless(QT_AVAILABLE, f"Runtime Qt indisponível: {QT_UNAVAILABLE_REASON}")
class SuspendedSaleDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view_model, _gateway = make_view_model()
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.suspended = self.view_model.suspend_sale()

    def test_enter_reabre_uma_vez_e_auto_repeat_nao_reabre(self):
        dialog = SuspendedSaleListDialog((self.suspended,))
        dialog.show()
        QApplication.processEvents()
        repeat = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier, "", True, 2,
        )
        QApplication.sendEvent(dialog.table, repeat)
        self.assertIsNone(dialog.selected_suspended_id)
        QTest.keyClick(dialog.table, Qt.Key.Key_Return)
        self.assertEqual(dialog.selected_suspended_id, "S1")
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_shift_enter_volta_sem_reabrir(self):
        dialog = SuspendedSaleListDialog((self.suspended,))
        dialog.show()
        dialog.resume_button.setFocus()
        QTest.keyClick(
            dialog.resume_button, Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
        )
        self.assertIsNone(dialog.selected_suspended_id)
        self.assertFalse(dialog.resume_button.hasFocus())
        dialog.close()

    def test_esc_fecha_somente_dialogo(self):
        window = PDVWindow(self.view_model)
        window.show()
        dialog = SuspendedSaleListDialog((self.suspended,), window)
        dialog.show()
        QApplication.processEvents()
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        QApplication.processEvents()
        self.assertFalse(dialog.isVisible())
        self.assertTrue(window.isVisible())
        window.close()


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
        self.assertEqual(shortcuts, {"Esc", "F4", "F5", "F6", "F7", "F9", "F10"})
        f6 = next(
            shortcut for shortcut in self.window._shortcuts
            if shortcut.key().toString() == "F6"
        )
        self.assertFalse(f6.autoRepeat())

    def test_f6_suspende_sem_cliente_sem_checkout_e_limpa_sessao(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        QTest.keyClick(self.window, Qt.Key.Key_F6)
        suspended = self.view_model.application.suspended_sales.open
        self.assertEqual(len(suspended), 1)
        self.assertIsNone(suspended[0].customer_id)
        self.assertTrue(self.view_model.session.cart.is_empty)
        self.assertEqual(self.gateway.commands, [])
        self.assertTrue(self.window.product_search.hasFocus())

    def test_clique_suspende_cliente_real_item_cadastrado_e_desconto(self):
        self._select_customer()
        self.view_model.session.add_item(
            CartItem("PRODUTO NOVE", 2, "10", product_id=9, discount_percent="5")
        )
        self.window.refresh_cart()
        QTest.mouseClick(self.window.suspend_button, Qt.MouseButton.LeftButton)
        suspended = self.view_model.application.suspended_sales.open[0]
        self.assertEqual(suspended.customer_id, 7)
        self.assertEqual(suspended.items[0].product_id, 9)
        self.assertEqual(suspended.items[0].discount_percent, Decimal("5.00"))
        self.assertEqual(self.gateway.commands, [])

    def test_carrinho_vazio_bloqueia_suspensao_e_foca_item(self):
        QTest.keyClick(self.window, Qt.Key.Key_F6)
        self.assertEqual(self.view_model.application.suspended_sales.open, [])
        self.assertTrue(self.window.product_search.hasFocus())

    def test_reabrir_sem_cliente_restaura_carrinho_e_foca_cliente(self):
        self.view_model.add_loose_item("SUSPENSO", "1", Decimal("10"))
        suspended = self.view_model.suspend_sale()
        self.window._clear_after_budget()
        FakeSuspendedSaleListDialog.selected_suspended_id = suspended.suspended_id
        with patch(
            "ui_qt.commercial.pdv_window.SuspendedSaleListDialog",
            FakeSuspendedSaleListDialog,
        ):
            self.window._open_suspended_sales()
        self.assertEqual(self.view_model.session.cart.items[0].description, "SUSPENSO")
        self.assertIsNone(self.view_model.session.customer_id)
        self.assertTrue(self.window.customer_search.hasFocus())
        self.assertEqual(self.gateway.commands, [])

    def test_reabrir_com_cliente_preserva_id_e_foca_finalizar(self):
        self._select_customer()
        self.view_model.add_loose_item("SUSPENSO", "1", Decimal("10"))
        suspended = self.view_model.suspend_sale()
        self.window._clear_after_budget()
        FakeSuspendedSaleListDialog.selected_suspended_id = suspended.suspended_id
        with patch(
            "ui_qt.commercial.pdv_window.SuspendedSaleListDialog",
            FakeSuspendedSaleListDialog,
        ):
            self.window._open_suspended_sales()
        self.assertEqual(self.view_model.session.customer_id, 7)
        self.assertEqual(self.view_model.selected_customer.customer_id, 7)
        self.assertTrue(self.window.checkout_button.hasFocus())
        self.assertEqual(self.gateway.commands, [])

    def test_cancelar_lista_nao_consume_venda_suspensa(self):
        self.view_model.add_loose_item("SUSPENSO", "1", Decimal("10"))
        self.view_model.suspend_sale()
        self.window._clear_after_budget()
        FakeSuspendedSaleListDialog.selected_suspended_id = None
        with patch(
            "ui_qt.commercial.pdv_window.SuspendedSaleListDialog",
            FakeSuspendedSaleListDialog,
        ):
            self.window._open_suspended_sales()
        self.assertEqual(len(self.view_model.application.suspended_sales.open), 1)
        self.assertTrue(self.view_model.session.cart.is_empty)

    def test_recusar_substituicao_preserva_carrinho_e_suspensa(self):
        self.view_model.add_loose_item("SUSPENSO", "1", Decimal("10"))
        suspended = self.view_model.suspend_sale()
        self.view_model.add_loose_item("ATUAL", "1", Decimal("5"))
        self.window.refresh_cart()
        FakeSuspendedSaleListDialog.selected_suspended_id = suspended.suspended_id
        with patch(
            "ui_qt.commercial.pdv_window.SuspendedSaleListDialog",
            FakeSuspendedSaleListDialog,
        ), patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No
        ):
            self.window._open_suspended_sales()
        self.assertEqual(self.view_model.session.cart.items[0].description, "ATUAL")
        self.assertEqual(len(self.view_model.application.suspended_sales.open), 1)

    def test_reaberta_so_chega_checkout_oficial_sem_persistencia_antecipada(self):
        self._select_customer()
        self.view_model.add_loose_item("SUSPENSO", "1", Decimal("10"))
        suspended = self.view_model.suspend_sale()
        self.window._clear_after_budget()
        FakeSuspendedSaleListDialog.selected_suspended_id = suspended.suspended_id
        with patch(
            "ui_qt.commercial.pdv_window.SuspendedSaleListDialog",
            FakeSuspendedSaleListDialog,
        ):
            self.window._open_suspended_sales()
        FakeCheckoutDialog.result = QDialog.DialogCode.Rejected
        with patch("ui_qt.commercial.pdv_window.CheckoutDialog", FakeCheckoutDialog):
            self.window._checkout()
        self.assertEqual(self.gateway.commands, [])
        self.assertEqual(len(self.view_model.session.cart.items), 1)

    def test_f5_alterna_modo_orcamento_e_f9_salva_sem_checkout(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        self.window._toggle_budget_mode()
        self.assertTrue(self.window._budget_mode)
        self.assertIn("ORÇAMENTO LIGADO", self.window.budget_button.text())
        self.assertIn("SALVAR ORÇAMENTO", self.window.checkout_button.text())
        FakeBudgetPreviewDialog.calls = []
        with patch("ui_qt.commercial.pdv_window.BudgetPreviewDialog", FakeBudgetPreviewDialog):
            self.window._conclude_action()
        self.assertEqual(len(self.view_model.application.budgets.open), 1)
        self.assertEqual(self.gateway.commands, [])
        self.assertTrue(self.view_model.session.cart.is_empty)
        self.assertEqual(FakeBudgetPreviewDialog.calls[0][0], "init")

    def test_enter_no_botao_salva_orcamento_exatamente_uma_vez(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        self.window._toggle_budget_mode()
        self.window.checkout_button.setFocus()
        FakeBudgetPreviewDialog.calls = []
        with patch("ui_qt.commercial.pdv_window.BudgetPreviewDialog", FakeBudgetPreviewDialog):
            QTest.keyClick(self.window.checkout_button, Qt.Key.Key_Return)
        self.assertEqual(len(self.view_model.application.budgets.open), 1)
        self.assertEqual(len(FakeBudgetPreviewDialog.calls), 2)
        self.assertEqual(self.gateway.commands, [])

    def test_atalho_f9_salva_orcamento_exatamente_uma_vez(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        self.window._toggle_budget_mode()
        FakeBudgetPreviewDialog.calls = []
        with patch("ui_qt.commercial.pdv_window.BudgetPreviewDialog", FakeBudgetPreviewDialog):
            QTest.keyClick(self.window, Qt.Key.Key_F9)
        self.assertEqual(len(self.view_model.application.budgets.open), 1)
        self.assertEqual(len(FakeBudgetPreviewDialog.calls), 2)
        self.assertEqual(self.gateway.commands, [])

    def test_clique_no_botao_salva_orcamento_sem_abrir_checkout(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        self.window._toggle_budget_mode()
        FakeBudgetPreviewDialog.calls = []
        with patch("ui_qt.commercial.pdv_window.BudgetPreviewDialog", FakeBudgetPreviewDialog):
            QTest.mouseClick(self.window.checkout_button, Qt.MouseButton.LeftButton)
        self.assertEqual(len(self.view_model.application.budgets.open), 1)
        self.assertEqual(self.gateway.commands, [])

    def test_enter_auto_repeat_no_salvar_orcamento_nao_duplica(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        self.window._toggle_budget_mode()
        self.window.checkout_button.setFocus()
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier,
            "", True, 2,
        )
        QApplication.sendEvent(self.window.checkout_button, event)
        self.assertEqual(self.view_model.application.budgets.open, [])
        self.assertEqual(len(self.view_model.session.cart.items), 1)

    def test_carregar_orcamento_prepara_venda_oficial_sem_finalizar(self):
        self._select_customer()
        self.view_model.add_loose_item("ORÇADO", "2", Decimal("10"))
        budget = self.view_model.save_budget()
        self.window._clear_after_budget()
        FakeBudgetListDialog.selected_budget_id = budget.budget_id
        with patch("ui_qt.commercial.pdv_window.BudgetListDialog", FakeBudgetListDialog):
            self.window._open_budgets()
        self.assertEqual(self.view_model.session.customer_id, 7)
        self.assertEqual(self.view_model.session.cart.items[0].description, "ORÇADO")
        self.assertFalse(self.window._budget_mode)
        self.assertEqual(self.gateway.commands, [])
        self.assertTrue(self.window.checkout_button.hasFocus())

    def test_carrinho_vazio_bloqueia_orcamento_e_foca_item(self):
        self.window._toggle_budget_mode()
        with patch("ui_qt.commercial.pdv_window.BudgetPreviewDialog") as preview:
            self.window._conclude_action()
        self.assertFalse(preview.called)
        self.assertEqual(self.view_model.application.budgets.open, [])
        self.assertTrue(self.window.product_search.hasFocus())

    def test_editar_item_avulso_atualiza_linha_e_invalida_pagamento(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.view_model.application.prepare_payments(
            self.view_model.session, [Payment(PaymentMethod.CASH, Decimal("10"))]
        )
        self.window.refresh_cart()
        self.window.cart.selectRow(0)
        with patch("ui_qt.commercial.pdv_window.CartItemDialog", FakeCartItemDialog):
            self.window._edit_selected_item()
        item = self.view_model.session.cart.items[0]
        self.assertEqual(item.quantity, Decimal("2"))
        self.assertEqual(item.unit_price, Decimal("15.00"))
        self.assertEqual(item.discount_percent, Decimal("10.00"))
        self.assertEqual(item.subtotal, Decimal("27.00"))
        self.assertIsNone(self.view_model.session.payment_plan)
        self.assertTrue(self.window.customer_search.hasFocus())

    def test_editar_item_no_orcamento_restaura_salvar_e_enter_funciona(self):
        self._cart_with_customer()
        self.window._toggle_budget_mode()
        self.window.cart.selectRow(0)
        with patch("ui_qt.commercial.pdv_window.CartItemDialog", FakeCartItemDialog):
            self.window._edit_selected_item()
        self.assertTrue(self.window.checkout_button.hasFocus())
        FakeBudgetPreviewDialog.calls = []
        with patch("ui_qt.commercial.pdv_window.BudgetPreviewDialog", FakeBudgetPreviewDialog):
            QTest.keyClick(self.window.checkout_button, Qt.Key.Key_Return)
        self.assertEqual(len(self.view_model.application.budgets.open), 1)
        self.assertEqual(self.gateway.commands, [])

    def test_cancelar_edicao_restaura_foco_operacional_do_orcamento(self):
        self._cart_with_customer()
        self.window._toggle_budget_mode()
        self.window.cart.selectRow(0)
        with patch(
            "ui_qt.commercial.pdv_window.CartItemDialog", FakeCancelledCartItemDialog
        ):
            self.window._edit_selected_item()
        self.assertEqual(len(self.view_model.session.cart.items), 1)
        self.assertTrue(self.window.checkout_button.hasFocus())

    def test_remover_item_restante_restaura_enter_para_salvar(self):
        self._select_customer()
        self.view_model.add_loose_item("ITEM 1", "1", Decimal("10"))
        self.view_model.add_loose_item("ITEM 2", "1", Decimal("5"))
        self.window.refresh_cart()
        self.window._toggle_budget_mode()
        self.window.cart.selectRow(0)
        self.window._remove_selected_item()
        self.assertEqual(len(self.view_model.session.cart.items), 1)
        self.assertTrue(self.window.checkout_button.hasFocus())
        FakeBudgetPreviewDialog.calls = []
        with patch("ui_qt.commercial.pdv_window.BudgetPreviewDialog", FakeBudgetPreviewDialog):
            QTest.keyClick(self.window.checkout_button, Qt.Key.Key_Return)
        self.assertEqual(len(self.view_model.application.budgets.open), 1)

    def test_clique_no_carrinho_enter_retorna_ao_proximo_passo_sem_dupla_acao(self):
        self._cart_with_customer()
        self.window._toggle_budget_mode()
        self.window.cart.selectRow(0)
        self.window.cart.setFocus()
        QTest.keyClick(self.window.cart, Qt.Key.Key_Return)
        self.assertTrue(self.window.checkout_button.hasFocus())
        self.assertEqual(self.view_model.application.budgets.open, [])
        FakeBudgetPreviewDialog.calls = []
        with patch("ui_qt.commercial.pdv_window.BudgetPreviewDialog", FakeBudgetPreviewDialog):
            QTest.keyClick(self.window.checkout_button, Qt.Key.Key_Return)
        self.assertEqual(len(self.view_model.application.budgets.open), 1)

    def test_trocar_texto_do_produto_preserva_fluxo_por_enter(self):
        self.window._toggle_budget_mode()
        self.window.product_search.setText("p9")
        self.window._select_product(self.window.product_results.item(0))
        self.window.product_search.setText("p9")
        self.assertIsNone(self.view_model.selected_product)
        self.window.product_search.setFocus()
        QTest.keyClick(self.window.product_search, Qt.Key.Key_Return)
        self.assertEqual(self.view_model.selected_product.product_id, 9)
        self.assertTrue(self.window.quantity.hasFocus())

    def test_delete_no_carrinho_remove_uma_vez_e_foca_entrada(self):
        self.view_model.add_loose_item("ITEM", "1", Decimal("10"))
        self.window.refresh_cart()
        self.window.cart.selectRow(0)
        self.window.cart.setFocus()
        QTest.keyClick(self.window.cart, Qt.Key.Key_Delete)
        QApplication.processEvents()
        self.assertTrue(self.view_model.session.cart.is_empty)
        self.assertEqual(self.window.cart.rowCount(), 0)
        self.assertTrue(self.window.product_search.hasFocus())

    def test_delete_auto_repeat_no_carrinho_nao_remove_item(self):
        self.view_model.add_loose_item("ITEM 1", "1", Decimal("10"))
        self.view_model.add_loose_item("ITEM 2", "1", Decimal("5"))
        self.window.refresh_cart()
        self.window.cart.selectRow(0)
        event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Delete,
            Qt.KeyboardModifier.NoModifier,
            "",
            True,
            2,
        )
        QApplication.sendEvent(self.window.cart, event)
        self.assertEqual(len(self.view_model.session.cart.items), 2)

    def test_preco_de_produto_cadastrado_fica_bloqueado_no_editor(self):
        self.view_model.select_product(FakeProducts.record.product_id)
        self.view_model.add_selected_product("1")
        dialog = CartItemDialog(self.view_model.session.cart.items[0], self.window)
        self.assertFalse(dialog.price.isEnabled())
        self.assertTrue(dialog.quantity.isEnabled())
        self.assertTrue(dialog.discount.isEnabled())
        dialog.close()

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

    def test_confirmacao_abre_pos_venda_uma_vez_sem_nova_persistencia(self):
        self._cart_with_customer()
        FakePostSaleDialog.calls = []
        with (
            patch("ui_qt.commercial.pdv_window.CheckoutDialog", FakeAcceptedCheckoutDialog),
            patch("ui_qt.commercial.pdv_window.PostSaleDialog", FakePostSaleDialog),
        ):
            self.window._checkout()
        self.assertEqual(len(self.gateway.commands), 1)
        self.assertEqual(
            [call[0] for call in FakePostSaleDialog.calls], ["init", "exec"]
        )
        self.assertTrue(self.view_model.session.cart.is_empty)

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
