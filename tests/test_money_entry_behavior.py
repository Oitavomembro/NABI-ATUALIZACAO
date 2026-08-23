import unittest
from decimal import Decimal

from services.money_entry_behavior import MoneyEntryBehavior


class FakeMoneyEntry:
    def __init__(self, value="", cursor=None):
        self.value = value
        self.cursor = len(value) if cursor is None else cursor
        self.bindings = {}

    def get(self):
        return self.value

    def delete(self, _start, _end):
        self.value = ""
        self.cursor = 0

    def insert(self, index, value):
        if index == 0:
            self.value = str(value)
        else:
            self.value = self.value[:index] + str(value) + self.value[index:]

    def index(self, position):
        if position != "insert":
            raise ValueError(position)
        return self.cursor

    def icursor(self, position):
        self.cursor = int(position)

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = (callback, add)


class MoneyEntryBehaviorTests(unittest.TestCase):
    def test_formata_digitos_imediatamente_em_real_brasileiro(self):
        for raw, expected in (
            ("2000", "2.000,00"),
            ("1000000", "1.000.000,00"),
        ):
            with self.subTest(raw=raw):
                entry = FakeMoneyEntry(raw)
                MoneyEntryBehavior.format_after_edit(entry)
                self.assertEqual(entry.value, expected)
                self.assertEqual(
                    getattr(entry, MoneyEntryBehavior._VALUE_ATTR),
                    Decimal(raw).quantize(Decimal("0.01")),
                )

    def test_ponto_de_milhar_nao_e_interpretado_como_decimal(self):
        self.assertEqual(MoneyEntryBehavior.parse("1.000"), Decimal("1000.00"))
        self.assertEqual(MoneyEntryBehavior.parse("1.000,50"), Decimal("1000.50"))

    def test_preserva_cursor_por_quantidade_de_digitos(self):
        entry = FakeMoneyEntry("1234", cursor=2)
        MoneyEntryBehavior.format_after_edit(entry)
        self.assertEqual(entry.value, "1.234,00")
        self.assertEqual(entry.cursor, 3)

    def test_attach_registra_um_unico_controlador_de_edicao(self):
        entry = FakeMoneyEntry("2000")
        MoneyEntryBehavior.attach(entry)
        MoneyEntryBehavior.attach(entry)
        self.assertEqual(list(entry.bindings), ["<KeyRelease>"])
        self.assertEqual(entry.bindings["<KeyRelease>"][1], "+")


if __name__ == "__main__":
    unittest.main()
