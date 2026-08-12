import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ItemAvulsoIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")

    def test_configuracao_expoe_modo_comercial_e_fiscal(self):
        self.assertIn("COMERCIAL — sem emissão fiscal", self.source)
        self.assertIn("FISCAL — com recursos fiscais", self.source)
        self.assertIn('salvar_config("modo_operacao"', self.source)

    def test_pdv_expoe_item_avulso_sem_estoque(self):
        self.assertIn("Produto avulso — não cadastra e não movimenta estoque", self.source)
        self.assertIn("def alternar_item_avulso_pdv", self.source)
        self.assertIn('"item_avulso": item_avulso', self.source)
        self.assertIn('"produto_id": None if item_avulso else produto_id', self.source)

    def test_modo_fiscal_bloqueia_item_avulso(self):
        self.assertIn("O modo fiscal não permite item avulso", self.source)
        self.assertIn("No modo fiscal, selecione um produto cadastrado com dados fiscais", self.source)


if __name__ == "__main__":
    unittest.main()
