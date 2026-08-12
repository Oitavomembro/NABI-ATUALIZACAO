import unittest

from core.enter_navigation import EnterField, IntelligentEnterNavigator


class FakeWidget:
    def __init__(self, state="normal", managed=True):
        self.state = state
        self.managed = managed
        self.focused = False
        self.bindings = {}

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
        pass

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback


class EnterNavigationTests(unittest.TestCase):
    def test_enter_advances_and_finishes_on_last_field(self):
        first, second = FakeWidget(), FakeWidget()
        finished = []
        navigator = IntelligentEnterNavigator([first, second], on_finish=lambda: finished.append(True))
        self.assertEqual(navigator.advance(first), "break")
        self.assertTrue(second.focused)
        self.assertFalse(finished)
        navigator.advance(second)
        self.assertEqual(finished, [True])

    def test_shift_enter_returns_to_previous_available_field(self):
        first, disabled, third = FakeWidget(), FakeWidget(state="disabled"), FakeWidget()
        navigator = IntelligentEnterNavigator([first, disabled, third], on_finish=lambda: None)
        navigator.previous(third)
        self.assertTrue(first.focused)
        self.assertFalse(disabled.focused)

    def test_validation_blocks_advance(self):
        first, second = FakeWidget(), FakeWidget()
        invalid = []
        navigator = IntelligentEnterNavigator(
            [EnterField(first, lambda: False), second],
            on_finish=lambda: None,
            on_invalid=lambda widget: invalid.append(widget),
        )
        navigator.advance(first)
        self.assertTrue(first.focused)
        self.assertFalse(second.focused)
        self.assertEqual(invalid, [first])

    def test_install_registers_enter_and_shift_enter(self):
        widget = FakeWidget()
        navigator = IntelligentEnterNavigator([widget], on_finish=lambda: None).install()
        self.assertTrue(navigator._installed)
        self.assertIn("<Return>", widget.bindings)
        self.assertIn("<KP_Enter>", widget.bindings)
        self.assertIn("<Shift-Return>", widget.bindings)


if __name__ == "__main__":
    unittest.main()
