from decimal import Decimal
import unittest

from commercial.domain.money import MoneyCodec, MoneyValueError


class CommercialMoneyTests(unittest.TestCase):
    def test_formatacao_zero_centavos_milhares_e_milhoes(self):
        cases = (
            (0, "0,00"),
            (1, "1,00"),
            (Decimal("10.5"), "10,50"),
            (1000, "1.000,00"),
            (1000000, "1.000.000,00"),
            ("0,01", "0,01"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(MoneyCodec.format_br(value), expected)

    def test_parsing_brasileiro_e_canonico_retorna_decimal_canonico(self):
        self.assertEqual(MoneyCodec.parse("1.234,56"), Decimal("1234.56"))
        self.assertEqual(MoneyCodec.parse("10.5"), Decimal("10.50"))
        self.assertEqual(MoneyCodec.parse("1.000.000"), Decimal("1000000.00"))
        self.assertEqual(MoneyCodec.canonical("10,5"), "10.50")

    def test_rejeita_invalidos_float_e_ambiguos(self):
        invalid = ("", "abc", "1.000", "1,000", "1,2,3", "1.234.56", 10.5, True, None)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(MoneyValueError):
                    MoneyCodec.parse(value)  # type: ignore[arg-type]

    def test_rejeita_precisao_superior_a_centavos(self):
        with self.assertRaises(MoneyValueError):
            MoneyCodec.parse(Decimal("10.001"))


if __name__ == "__main__":
    unittest.main()
