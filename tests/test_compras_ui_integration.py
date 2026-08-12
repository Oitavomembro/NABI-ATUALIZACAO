from __future__ import annotations

import ast
import unittest
from pathlib import Path


class ComprasUIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_path = Path(__file__).resolve().parents[1] / "nabicode_legacy.py"
        cls.source = cls.source_path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.methods = {
            node.name
            for node in ast.walk(cls.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_tela_compras_esta_integrada_ao_roteamento(self) -> None:
        self.assertIn("tela_compras", self.methods)
        self.assertIn("carregar_compras", self.methods)
        self.assertIn('self.telas["compras"] = self.tela_compras', self.source)
        self.assertIn('elif nome == "compras":', self.source)

    def test_tela_compras_tem_layout_universal_e_acoes_reais(self) -> None:
        for method in (
            "novo_pedido_compra",
            "receber_pedido_compra",
            "abrir_detalhes_compra",
        ):
            self.assertIn(method, self.methods)
        self.assertIn("BidirectionalScrollableFrame", self.source)
        self.assertIn("UniversalLayoutPolicy.metrics", self.source)
        self.assertIn("COMPRA_SERVICE.criar_pedido", self.source)
        self.assertIn("COMPRA_SERVICE.receber", self.source)


if __name__ == "__main__":
    unittest.main()
