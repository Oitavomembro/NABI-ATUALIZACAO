from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from commercial.application.dto import (
    CheckoutCommand,
    CheckoutReceipt,
    CheckoutResult,
    CustomerRecord,
)
from commercial.domain.cart import CartItem
from commercial.domain.credit import CreditInstallment, CreditTerms
from commercial.domain.payments import Payment, PaymentMethod, PaymentPlan


class CommercialCreditTests(unittest.TestCase):
    def test_formas_outros_cartoes_e_autorizacao_opcional(self):
        self.assertEqual(Payment(PaymentMethod.OTHER, "10").method.value, "OUTROS")
        self.assertEqual(Payment(PaymentMethod.DEBIT, "10").card_authorization, "")
        card = Payment(PaymentMethod.CREDIT_CARD, "10", " NSU123 ")
        self.assertEqual(card.card_authorization, "NSU123")
        with self.assertRaisesRegex(ValueError, "20 caracteres"):
            Payment(PaymentMethod.DEBIT, "10", "X" * 21)
        with self.assertRaisesRegex(ValueError, "cartão"):
            Payment(PaymentMethod.PIX, "10", "NSU")

    def test_pagamento_misto_troco_e_soma_divergente(self):
        plan = PaymentPlan([
            Payment(PaymentMethod.PIX, "40"), Payment(PaymentMethod.CASH, "70")
        ])
        validation = plan.validate_against("100")
        self.assertEqual(validation.received, Decimal("110.00"))
        self.assertEqual(validation.change, Decimal("10.00"))
        with self.assertRaisesRegex(ValueError, "não atingem"):
            PaymentPlan([Payment(PaymentMethod.PIX, "99")]).validate_against("100")

    def test_uma_parcela(self):
        terms = CreditTerms.create(
            down_payment=Decimal("0"),
            financed_value=Decimal("100.00"),
            due_dates=[date(2026, 9, 22)],
        )
        self.assertEqual(terms.installment_count, 1)
        self.assertEqual(terms.installments[0].amount, Decimal("100.00"))

    def test_varias_parcelas_distribuem_centavos_residuais_com_soma_exata(self):
        terms = CreditTerms.create(
            down_payment=Decimal("10.00"),
            financed_value=Decimal("100.00"),
            due_dates=[date(2026, 9, 22), date(2026, 10, 22), date(2026, 11, 22)],
        )
        self.assertEqual(
            tuple(item.amount for item in terms.installments),
            (Decimal("33.34"), Decimal("33.33"), Decimal("33.33")),
        )
        self.assertEqual(sum(item.amount for item in terms.installments), terms.financed_value)

    def test_construtor_rejeita_soma_divergente(self):
        with self.assertRaises(ValueError):
            CreditTerms(
                down_payment=Decimal("0"),
                financed_value=Decimal("10.00"),
                installments=(CreditInstallment(1, date(2026, 9, 22), Decimal("9.99")),),
            )


class CommercialCheckoutDtoTests(unittest.TestCase):
    def test_checkout_entrada_crediario_e_resultado_imutaveis(self):
        items = (CartItem("Produto", Decimal("1"), Decimal("500.00"), product_id=1),)
        plan = PaymentPlan([
            Payment(PaymentMethod.PIX, Decimal("100.00")),
            Payment(PaymentMethod.STORE_CREDIT, Decimal("400.00")),
        ])
        terms = CreditTerms.create(
            down_payment=Decimal("100.00"),
            financed_value=Decimal("400.00"),
            due_dates=[date(2026, 9, 22), date(2026, 10, 22)],
        )
        command = CheckoutCommand(
            customer_id=7,
            items=items,
            payment_plan=plan,
            credit_terms=terms,
        )
        customer = CustomerRecord(7, "C7", "CLIENTE")
        receipt = CheckoutReceipt(
            sale_id=10,
            customer=customer,
            items=items,
            payments=plan.payments,
            total=command.final_total,
            financed_value=plan.financed_value,
            received=Decimal("500.00"),
            change=Decimal("0.00"),
            payment_description="PIX + CREDIARIO",
            status="concluida",
        )
        result = CheckoutResult(
            success=True,
            committed=True,
            sale_id=10,
            total=command.final_total,
            financed_value=plan.financed_value,
            received=Decimal("500.00"),
            change=Decimal("0.00"),
            message="Venda confirmada.",
            status="concluida",
            session_consumed=True,
            receipt=receipt,
        )
        self.assertEqual(command.final_total, Decimal("500.00"))
        self.assertEqual(result.status, "CONCLUIDA")
        with self.assertRaises(FrozenInstanceError):
            command.customer_id = 8  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.status = "OUTRO"  # type: ignore[misc]

    def test_checkout_normaliza_desconto_acrescimo_e_valida_composicao(self):
        item = CartItem("Produto", Decimal("1"), Decimal("100.00"))
        plan = PaymentPlan([Payment(PaymentMethod.CASH, Decimal("95.00"))])
        command = CheckoutCommand(
            customer_id=1,
            items=[item],
            payment_plan=plan,
            discount_amount="10,00",
            surcharge_amount="5,00",
        )
        self.assertEqual(command.final_total, Decimal("95.00"))
        with self.assertRaises(ValueError):
            CheckoutCommand(
                customer_id=1,
                items=[item],
                payment_plan=PaymentPlan([Payment(PaymentMethod.PIX, Decimal("94.00"))]),
                discount_amount=Decimal("10.00"),
                surcharge_amount=Decimal("5.00"),
            )

    def test_commercial_nao_importa_gui_sqlite_ou_sdk_de_ia(self):
        root = Path(__file__).resolve().parents[1] / "commercial"
        forbidden = (
            "tkinter", "customtkinter", "pyside", "pyqt", "sqlite3",
            "openai", "anthropic", "google.generativeai",
        )
        for source_path in root.rglob("*.py"):
            source = source_path.read_text(encoding="utf-8").casefold()
            for dependency in forbidden:
                with self.subTest(file=source_path.name, dependency=dependency):
                    self.assertNotIn(f"import {dependency}", source)
                    self.assertNotIn(f"from {dependency}", source)


if __name__ == "__main__":
    unittest.main()
