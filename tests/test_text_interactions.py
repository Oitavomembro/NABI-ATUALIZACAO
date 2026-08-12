import unittest

from core.text_interactions import normalize_decimal_text, UniversalTextInteractionManager


class FakeRoot:
    def bind_all(self, sequence, callback, add=None):
        return f"bind:{sequence}"

    def bind_class(self, class_name, sequence, callback):
        return f"bind:{class_name}:{sequence}"


class TextInteractionTests(unittest.TestCase):
    def test_normalize_currency_brazilian(self):
        self.assertEqual(normalize_decimal_text("R$ 1.234,56"), "1234.56")

    def test_normalize_percentage(self):
        self.assertEqual(normalize_decimal_text("- 35,5 %"), "-35.5")

    def test_normalize_us_decimal(self):
        self.assertEqual(normalize_decimal_text("12.50"), "12.50")

    def test_install_is_idempotent(self):
        manager = UniversalTextInteractionManager(FakeRoot())
        manager.install()
        manager.install()
        self.assertTrue(manager.installed)

    def test_supported_widget_classes(self):
        class Widget:
            def __init__(self, name): self.name = name
            def winfo_class(self): return self.name
        self.assertTrue(UniversalTextInteractionManager._supported(Widget("Entry")))
        self.assertTrue(UniversalTextInteractionManager._supported(Widget("Text")))
        self.assertTrue(UniversalTextInteractionManager._supported(Widget("Treeview")))
        self.assertFalse(UniversalTextInteractionManager._supported(Widget("Frame")))


if __name__ == "__main__":
    unittest.main()
