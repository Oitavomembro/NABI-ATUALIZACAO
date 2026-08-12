from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
REPOSITORY = (ROOT / "repositories" / "produto_repository.py").read_text(encoding="utf-8")
CONTROLLER = (ROOT / "services" / "product_pricing_controller.py").read_text(encoding="utf-8")


class ProductAutoPriceRegressionTests(unittest.TestCase):
    def test_auto_price_uses_reusable_controller(self):
        self.assertIn("ProductPricingController", LEGACY)
        self.assertIn("controlador_preco.on_cost_or_margin_changed", LEGACY)
        self.assertIn("controlador_preco.on_sale_price_changed", LEGACY)
        self.assertNotIn("_calculando_preco", LEGACY)
        self.assertIn("class ProductPricingController", CONTROLLER)

    def test_legacy_description_compatibility_is_preserved(self):
        self.assertIn('_produto_tem_coluna("descricao", connection)', REPOSITORY)
        self.assertIn('valores.insert(2,dados["nome"])', REPOSITORY)


if __name__ == "__main__":
    unittest.main()
