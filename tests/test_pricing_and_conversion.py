import unittest

from services import PricingService, UnitConversionService


class PricingAndConversionTests(unittest.TestCase):
    def test_precificacao_com_despesas_e_margem(self):
        result = PricingService.calcular(100, 10, 20)
        self.assertEqual(float(result.despesas), 10.0)
        self.assertEqual(float(result.custo_total), 110.0)
        self.assertEqual(float(result.lucro), 22.0)
        self.assertEqual(float(result.preco_sugerido), 132.0)

    def test_arredondamento_financeiro(self):
        result = PricingService.calcular(10.01, 3, 17)
        self.assertEqual(float(result.preco_sugerido), 12.06)

    def test_validacoes_precificacao(self):
        with self.assertRaises(ValueError):
            PricingService.calcular(-1, 0, 0)
        with self.assertRaises(ValueError):
            PricingService.calcular(1, 0, 1001)

    def test_conversao_e_custo_unitario(self):
        self.assertEqual(UnitConversionService.para_estoque(2, 12), 24.0)
        self.assertEqual(UnitConversionService.custo_unitario_estoque(120, 12), 10.0)


if __name__ == "__main__":
    unittest.main()
