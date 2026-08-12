import unittest

from services.product_pricing_controller import ProductPricingController, ProductPricingControls


class FakeEntry:
    def __init__(self, value=""):
        self.value = str(value)
        self.writes = 0

    def get(self):
        return self.value

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = str(value)
        self.writes += 1


class CallbackEntry(FakeEntry):
    def __init__(self, value=""):
        super().__init__(value)
        self.callback = None

    def insert(self, _index, value):
        super().insert(_index, value)
        if self.callback:
            self.callback()


class ProductPricingControllerTests(unittest.TestCase):
    def make_controller(self, custo="100", despesas="10", margem="20", preco="0"):
        controls = ProductPricingControls(
            custo=FakeEntry(custo),
            despesas_percentual=FakeEntry(despesas),
            margem_lucro=FakeEntry(margem),
            preco_venda=FakeEntry(preco),
        )
        return ProductPricingController(controls), controls

    def test_calculates_and_writes_sale_price(self):
        controller, controls = self.make_controller()
        state = controller.on_cost_or_margin_changed()
        self.assertEqual(state.preco_venda, "132")
        self.assertEqual(controls.preco_venda.get(), "132,00")

    def test_calculates_and_writes_margin(self):
        controller, controls = self.make_controller(preco="132")
        state = controller.on_sale_price_changed()
        self.assertEqual(state.margem_lucro, "20")
        self.assertEqual(controls.margem_lucro.get(), "20,00")

    def test_automatic_callback_ignores_invalid_input(self):
        controller, controls = self.make_controller(margem="abc", preco="77")
        self.assertIsNone(controller.on_cost_or_margin_changed())
        self.assertEqual(controls.preco_venda.get(), "77")

    def test_manual_suggestion_reports_invalid_or_zero_cost(self):
        controller, _ = self.make_controller(custo="0")
        with self.assertRaisesRegex(ValueError, "maior que zero"):
            controller.apply_suggested_price()

    def test_recursion_guard_prevents_nested_recalculation(self):
        controller, controls = self.make_controller()
        controller._updating = True
        try:
            self.assertIsNone(controller.on_cost_or_margin_changed())
            self.assertEqual(controls.preco_venda.writes, 0)
        finally:
            controller._updating = False

    def test_does_not_rewrite_same_formatted_value(self):
        controller, controls = self.make_controller(preco="132,00")
        controller.on_cost_or_margin_changed()
        self.assertEqual(controls.preco_venda.writes, 0)

    def test_real_nested_callback_is_blocked_during_widget_write(self):
        controls = ProductPricingControls(
            custo=FakeEntry("100"), despesas_percentual=FakeEntry("10"),
            margem_lucro=FakeEntry("20"), preco_venda=CallbackEntry("0"),
        )
        controller = ProductPricingController(controls)
        controls.preco_venda.callback = controller.on_sale_price_changed
        state = controller.on_cost_or_margin_changed()
        self.assertEqual(state.preco_venda, "132")
        self.assertEqual(controls.preco_venda.get(), "132,00")
        self.assertEqual(controls.margem_lucro.writes, 0)

    def test_controls_validate_required_entry_protocol(self):
        with self.assertRaisesRegex(TypeError, "Controle de preço incompatível"):
            ProductPricingControls(object(), FakeEntry(), FakeEntry(), FakeEntry())

    def test_decimal_formatting_does_not_use_binary_float(self):
        controller, controls = self.make_controller(custo="0,10", despesas="0", margem="10")
        controller.on_cost_or_margin_changed()
        self.assertEqual(controls.preco_venda.get(), "0,11")


if __name__ == "__main__":
    unittest.main()
