import unittest

from core.enter_navigation import IntelligentEnterNavigator
from services.search_entry_behavior import SearchEntryBehavior
from ui.keyboard_navigation import bind_enter_pair


class FakeWidget:
    def __init__(self, state="normal", managed=True):
        self.state = state
        self.managed = managed
        self.focused = False
        self.bindings = {}
        self.bind_calls = []
        self.value = ""

    def cget(self, key):
        if key == "state":
            return self.state
        raise KeyError(key)

    def winfo_exists(self):
        return True

    def winfo_manager(self):
        return "grid" if self.managed else ""

    def focus_set(self):
        self.focused = True

    def select_range(self, _start, _end):
        return None

    def selection_range(self, _start, _end):
        return None

    def icursor(self, _where):
        return None

    def get(self):
        return self.value

    def configure(self, **_kwargs):
        return None

    def bind(self, sequence, callback, add=None):
        self.bind_calls.append((sequence, add))
        self.bindings.setdefault(sequence, []).append(callback)

    def fire(self, sequence):
        result = None
        event = type("Event", (), {"widget": self})()
        for callback in list(self.bindings.get(sequence, [])):
            result = callback(event)
            if result == "break":
                break
        return result


class PDVKeyboardNavigation2490Tests(unittest.TestCase):
    def test_enter_and_keypad_enter_have_identical_callbacks(self):
        widget = FakeWidget()
        calls = []
        bind_enter_pair(widget, lambda _event: calls.append("advance") or "break", owner="pdv")

        self.assertEqual(widget.fire("<Return>"), "break")
        self.assertEqual(widget.fire("<KP_Enter>"), "break")
        self.assertEqual(calls, ["advance", "advance"])

    def test_same_binding_owner_is_not_registered_twice(self):
        widget = FakeWidget()
        callback = lambda _event: "break"
        bind_enter_pair(widget, callback, owner="pdv")
        bind_enter_pair(widget, callback, owner="pdv")

        self.assertEqual(len(widget.bindings["<Return>"]), 1)
        self.assertEqual(len(widget.bindings["<KP_Enter>"]), 1)

    def test_search_entry_attach_is_idempotent_for_enter(self):
        entry = FakeWidget()
        calls = []
        SearchEntryBehavior.attach(entry, on_enter=lambda: calls.append("search"))
        SearchEntryBehavior.attach(entry, on_enter=lambda: calls.append("duplicate"))

        self.assertEqual(len(entry.bindings["<Return>"]), 1)
        self.assertEqual(len(entry.bindings["<KP_Enter>"]), 1)
        entry.fire("<Return>")
        self.assertEqual(calls, ["search"])

    def test_quantity_price_add_and_return_to_product_with_enter_only(self):
        product = FakeWidget()
        quantity = FakeWidget()
        price = FakeWidget()
        steps = []

        def add_item():
            steps.append("add")
            product.focus_set()

        navigator = IntelligentEnterNavigator(
            [quantity, price],
            on_finish=add_item,
        ).install()

        self.assertEqual(quantity.fire("<Return>"), "break")
        self.assertTrue(price.focused)
        self.assertEqual(price.fire("<Return>"), "break")
        self.assertEqual(steps, ["add"])
        self.assertTrue(product.focused)
        self.assertTrue(navigator._installed)

    def test_quantity_price_add_and_return_to_product_with_keypad_enter_only(self):
        product = FakeWidget()
        quantity = FakeWidget()
        price = FakeWidget()
        steps = []

        def add_item():
            steps.append("add")
            product.focus_set()

        IntelligentEnterNavigator([quantity, price], on_finish=add_item).install()

        self.assertEqual(quantity.fire("<KP_Enter>"), "break")
        self.assertTrue(price.focused)
        self.assertEqual(price.fire("<KP_Enter>"), "break")
        self.assertEqual(steps, ["add"])
        self.assertTrue(product.focused)


if __name__ == "__main__":
    unittest.main()
