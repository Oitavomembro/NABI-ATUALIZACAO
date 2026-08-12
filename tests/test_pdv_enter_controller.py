from types import SimpleNamespace

from controllers.pdv_enter_controller import PDVEnterController


class FakeWidget:
    def __init__(self, value=""):
        self.value = value
        self.bindings = {}
        self.focused = False
        self.selected = False
        self.children = []

    def get(self):
        return self.value

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = (callback, add)

    def focus_set(self):
        self.focused = True

    def select_range(self, start, end):
        self.selected = (start, end) == (0, "end")

    def get_children(self):
        return tuple(self.children)


class FakePopup:
    def __init__(self, exists=True):
        self.exists = exists

    def winfo_exists(self):
        return self.exists


def build_controller(*, product="ABC", popup=None, barcode=True, qty_valid=True, price_valid=True):
    widgets = {name: FakeWidget() for name in ("qty", "price", "cart")}
    widgets["product"] = FakeWidget(product)
    calls = []
    controller = PDVEnterController(
        product_entry=widgets["product"],
        quantity_entry=widgets["qty"],
        price_entry=widgets["price"],
        cart=widgets["cart"],
        popup_getter=lambda: popup,
        confirm_suggestion=lambda event=None: calls.append(("suggestion", event)),
        select_by_barcode=lambda term: calls.append(("barcode", term)) or barcode,
        add_item=lambda: calls.append(("add", None)),
        finalize_sale=lambda: calls.append(("finalize", None)),
        validate_quantity=lambda: qty_valid,
        validate_price=lambda: price_valid,
    )
    return controller, widgets, calls


def test_install_is_single_owner_for_return_and_keypad_enter():
    controller, widgets, _ = build_controller()
    controller.install()
    for widget in widgets.values():
        assert set(widget.bindings) == {"<Return>", "<KP_Enter>"}
        assert widget.bindings["<Return>"][1] is None
        assert widget.bindings["<KP_Enter>"][1] is None


def test_product_to_quantity_to_price_to_add_flow():
    controller, widgets, calls = build_controller()
    assert controller.handle_product() == "break"
    assert calls == [("barcode", "ABC")]
    assert widgets["qty"].focused and widgets["qty"].selected

    assert controller.handle_quantity() == "break"
    assert widgets["price"].focused and widgets["price"].selected

    assert controller.handle_price() == "break"
    assert calls[-1] == ("add", None)


def test_open_suggestion_consumes_enter_without_barcode_path():
    popup = FakePopup(True)
    controller, _, calls = build_controller(popup=popup)
    event = SimpleNamespace(widget=None)
    assert controller.handle_product(event) == "break"
    assert calls == [("suggestion", None)]


def test_invalid_quantity_or_price_blocks_advance():
    controller, widgets, calls = build_controller(qty_valid=False, price_valid=False)
    controller.handle_quantity()
    assert widgets["qty"].focused
    controller.handle_price()
    assert widgets["price"].focused
    assert ("add", None) not in calls


def test_cart_enter_finalizes_and_legacy_adapter_dispatches():
    controller, widgets, calls = build_controller()
    event = SimpleNamespace(widget=widgets["cart"])
    assert controller.dispatch_legacy_event(event) == "break"
    assert calls == [("finalize", None)]


def test_empty_product_with_cart_moves_to_finalization_then_enter_finalizes():
    controller, widgets, calls = build_controller(product="", popup=None, barcode=False)
    widgets["cart"].children = ["item-1"]
    assert controller.handle_product() == "break"
    assert widgets["cart"].focused
    assert controller.handle_cart() == "break"
    assert calls == [("finalize", None)]
