from decimal import Decimal
import unittest

from commercial.domain.payments import Payment, PaymentMethod, PaymentPlan


class CommercialPaymentTests(unittest.TestCase):
    def test_todas_as_formas_simples(self):
        for method in PaymentMethod:
            with self.subTest(method=method):
                plan = PaymentPlan([Payment(method, Decimal("100.00"))])
                validation = plan.validate_against(Decimal("100.00"))
                expected_financed = Decimal("100.00") if method is PaymentMethod.STORE_CREDIT else Decimal("0.00")
                self.assertEqual(validation.financed_value, expected_financed)

    def test_multiplas_formas_e_troco_em_dinheiro(self):
        plan = PaymentPlan([
            Payment(PaymentMethod.PIX, Decimal("40.00")),
            Payment(PaymentMethod.CASH, Decimal("70.00")),
        ])
        validation = plan.validate_against(Decimal("100.00"))
        self.assertEqual(plan.total, Decimal("110.00"))
        self.assertEqual(validation.received, Decimal("110.00"))
        self.assertEqual(validation.change, Decimal("10.00"))

    def test_entrada_mais_crediario_calcula_somente_financiado(self):
        plan = PaymentPlan([
            Payment(PaymentMethod.PIX, Decimal("100.00")),
            Payment(PaymentMethod.STORE_CREDIT, Decimal("400.00")),
        ])
        validation = plan.validate_against(Decimal("500.00"))
        self.assertEqual(plan.financed_value, Decimal("400.00"))
        self.assertEqual(plan.entrance_value(Decimal("500.00")), Decimal("100.00"))
        self.assertEqual(validation.change, Decimal("0.00"))

    def test_rejeita_negativo_zero_divergencia_e_troco_nao_monetario(self):
        for invalid in (Decimal("-1"), Decimal("0")):
            with self.assertRaises(ValueError):
                Payment(PaymentMethod.CASH, invalid)
        with self.assertRaises(ValueError):
            PaymentPlan([]).validate_against(Decimal("10.00"))
        with self.assertRaises(ValueError):
            PaymentPlan([Payment(PaymentMethod.PIX, Decimal("9.99"))]).validate_against(Decimal("10.00"))
        with self.assertRaises(ValueError):
            PaymentPlan([Payment(PaymentMethod.PIX, Decimal("10.01"))]).validate_against(Decimal("10.00"))
        with self.assertRaises(ValueError):
            PaymentPlan([
                Payment(PaymentMethod.CASH, Decimal("10.00")),
                Payment(PaymentMethod.STORE_CREDIT, Decimal("5.00")),
            ]).validate_against(Decimal("20.00"))


if __name__ == "__main__":
    unittest.main()
