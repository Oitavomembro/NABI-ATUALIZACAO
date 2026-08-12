import unittest
from decimal import Decimal

from repositories.produto_repository import ProdutoRepository
from services.product_application_service import ProductApplicationService, ProductFormData


class ProductDecimalPipelineTests(unittest.TestCase):
    def test_form_numbers_are_parsed_without_binary_float(self):
        command = ProductApplicationService.criar_comando(ProductFormData(
            codigo="1", nome="Produto Decimal", preco_venda="1234,56",
            categoria_id=None, tipo_produto="MERCADORIA",
            preco_custo="0,1", despesas_percentual="10,25",
            margem_lucro="20,15", fator_conversao="1,5",
        ))
        self.assertIsInstance(command.preco_venda, Decimal)
        self.assertEqual(command.preco_venda, Decimal("1234.56"))
        self.assertEqual(command.preco_custo, Decimal("0.1"))
        self.assertEqual(command.despesas_percentual, Decimal("10.25"))
        self.assertEqual(command.margem_lucro, Decimal("20.15"))
        self.assertEqual(command.fator_conversao, Decimal("1.5"))

    def test_decimal_formatter_preserves_integer_zeroes(self):
        self.assertEqual(ProductApplicationService.formatar_numero_formulario(Decimal("20")), "20")
        self.assertEqual(ProductApplicationService.formatar_numero_formulario(Decimal("20.5000")), "20,5")

    def test_repository_serializes_decimal_without_float(self):
        self.assertEqual(ProdutoRepository._sqlite_decimal(Decimal("0.1000000000000000001")), "0.1000000000000000001")
        self.assertEqual(
            ProdutoRepository._sqlite_values([Decimal("1234.56"), "texto", 3]),
            ["1234.56", "texto", 3],
        )

    def test_non_finite_decimal_is_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ProductApplicationService.converter_decimal(value)


if __name__ == "__main__":
    unittest.main()
