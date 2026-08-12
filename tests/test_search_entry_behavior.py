import unittest

from services.search_entry_behavior import SearchEntryBehavior


class FakeEvent:
    def __init__(self, widget):
        self.widget = widget


class FakeEntry:
    def __init__(self, value=""):
        self.value = value
        self.config = {}
        self.selected = None
        self.cursor = None
        self.bindings = {}

    def configure(self, **kwargs):
        self.config.update(kwargs)

    def get(self):
        return self.value

    def select_range(self, start, end):
        self.selected = (start, end)

    def icursor(self, position):
        self.cursor = position

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = (callback, add)


class FakeNativeEntry(FakeEntry):
    def configure(self, **kwargs):
        if "text_color" in kwargs or "placeholder_text_color" in kwargs:
            raise RuntimeError("unknown option -text_color")
        self.config.update(kwargs)


class SearchEntryBehaviorTests(unittest.TestCase):
    def test_configures_placeholder_and_typed_text_colors(self):
        entry = FakeEntry()
        SearchEntryBehavior.configure(entry)
        self.assertEqual(entry.config["text_color"], "#ffffff")
        self.assertEqual(entry.config["placeholder_text_color"], "#8b949e")

    def test_native_tk_entry_uses_supported_color_options(self):
        entry = FakeNativeEntry()
        SearchEntryBehavior.configure(entry)
        self.assertEqual(entry.config["fg"], "#ffffff")
        self.assertEqual(entry.config["insertbackground"], "#ffffff")
        self.assertNotIn("text_color", entry.config)

    def test_focus_selects_previous_search_without_treating_placeholder_as_value(self):
        entry = FakeEntry("Cliente selecionado")
        self.assertIsNone(SearchEntryBehavior.select_existing_text(entry))
        self.assertEqual(entry.selected, (0, "end"))
        self.assertEqual(entry.config["text_color"], "#ffffff")

    def test_empty_placeholder_focus_is_not_consumed_and_restores_typed_color(self):
        entry = FakeEntry("")
        SearchEntryBehavior.attach_focus(entry)
        callback = entry.bindings["<FocusIn>"][0]
        self.assertIsNone(callback(FakeEvent(entry)))
        self.assertIsNone(entry.selected)
        self.assertEqual(entry.config["text_color"], "#ffffff")

    def test_enter_is_always_consumed(self):
        self.assertEqual(SearchEntryBehavior.consume_enter(), "break")

    def test_attach_binds_normal_and_keypad_enter_and_focus(self):
        calls = []
        entry = FakeEntry("Produto anterior")
        SearchEntryBehavior.attach(entry, on_enter=lambda: calls.append("enter"))

        self.assertIn("<FocusIn>", entry.bindings)
        self.assertIn("<Return>", entry.bindings)
        self.assertIn("<KP_Enter>", entry.bindings)
        self.assertEqual(entry.bindings["<Return>"][1], "+")

        focus_callback = entry.bindings["<FocusIn>"][0]
        self.assertIsNone(focus_callback(FakeEvent(entry)))
        self.assertEqual(entry.selected, (0, "end"))

        for sequence in ("<Return>", "<KP_Enter>"):
            callback = entry.bindings[sequence][0]
            self.assertEqual(callback(FakeEvent(entry)), "break")
        self.assertEqual(calls, ["enter", "enter"])


if __name__ == "__main__":
    unittest.main()
