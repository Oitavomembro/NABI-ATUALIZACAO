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
        self.assertIn('"compras": self.tela_compras', self.source)
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

    def test_compras_abre_cadastro_oficial_diretamente_em_fornecedores(self) -> None:
        self.assertIn('text="Fornecedores", command=self.abrir_fornecedores_compras', self.source)
        self.assertIn('self.abrir_cadastros_auxiliares("fornecedor", ao_fechar=ao_fechar)', self.source)
        self.assertIn('self._autorizar("compras", "create")', self.source)

    def test_pedido_sem_fornecedor_oferece_cadastro_e_retoma_fluxo(self) -> None:
        self.assertIn("Deseja cadastrar um fornecedor agora?", self.source)
        self.assertIn("self.abrir_fornecedores_compras(retomar_pedido=True)", self.source)
        self.assertIn("if retomar_pedido and COMPRA_SERVICE.repository.listar_fornecedores():", self.source)
        self.assertIn("self.novo_pedido_compra()", self.source)

    def test_produtos_preserva_marcas_fornecedores_e_unidades(self) -> None:
        self.assertIn('values=["marca", "fornecedor", "unidade"]', self.source)
        self.assertIn('def abrir_cadastros_auxiliares(self, tipo_inicial="marca", ao_fechar=None):', self.source)
        self.assertIn("COMPRA_SERVICE.receber", self.source)


if __name__ == "__main__":
    unittest.main()
