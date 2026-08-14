import ast
import unittest
from pathlib import Path


class FinanceiroUIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("nabicode_legacy.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.methods = {node.name for node in ast.walk(cls.tree) if isinstance(node, ast.FunctionDef)}

    def test_tela_financeiro_esta_registrada(self):
        self.assertIn('"financeiro": self.tela_financeiro', self.source)
        self.assertIn('self.botoes_topo["financeiro"]', self.source)

    def test_operacoes_financeiras_expostas(self):
        esperados = {
            "tela_financeiro", "carregar_financeiro", "novo_titulo_financeiro",
            "baixar_titulo_financeiro", "definir_centro_custo_financeiro",
            "abrir_recorrencias_financeiro", "conciliar_pagamento_financeiro",
        }
        self.assertTrue(esperados.issubset(self.methods))

    def test_pesquisa_global_inclui_financeiro(self):
        self.assertIn('CommandDefinition("financeiro", "Abrir Financeiro"', self.source)


if __name__ == "__main__":
    unittest.main()
