from decimal import Decimal
import unittest

from repositories.decimal_storage import DecimalStorage, DecimalStorageError


class DecimalStorageTests(unittest.TestCase):
    def test_canonical_preserves_precision_and_removes_only_fractional_zeros(self):
        self.assertEqual(DecimalStorage.canonical(Decimal("20.0000")), "20")
        self.assertEqual(DecimalStorage.canonical(Decimal("0.1000000000000000001")), "0.1000000000000000001")

    def test_rejects_non_finite_values(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(DecimalStorageError):
                DecimalStorage.canonical(value)
