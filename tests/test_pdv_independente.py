import ast
from pathlib import Path
import unittest


class PDVIndependenteEstruturaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("nabicode_legacy.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.app = next(
            node for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp"
        )
        cls.methods = {
            node.name: node for node in cls.app.body if isinstance(node, ast.FunctionDef)
        }

    def test_pdv_possui_ciclo_de_vida_independente(self):
        for method_name in (
            "abrir_pdv_independente",
            "_fechar_pdv",
            "_alternar_tela_cheia_pdv",
            "remover_item_carrinho_selecionado",
            "abrir_cliente_rapido_pdv",
            "aplicar_desconto_item_pdv",
            "alterar_quantidade_item_pdv",
            "_enter_contexto_pdv",
            "_selecionar_produto_por_codigo_barras",
        ):
            self.assertIn(method_name, self.methods)

    def test_pdv_possui_atalhos_e_preserva_venda(self):
        method_source = ast.get_source_segment(
            self.source, self.methods["abrir_pdv_independente"]
        ) or ""
        close_source = ast.get_source_segment(
            self.source, self.methods["_fechar_pdv"]
        ) or ""
        for binding in ("<Delete>", "<F2>", "<F3>", "<Shift-F3>", "<F4>", "<F5>", "<F6>", "<F7>", "<F9>", "<F10>", "<F11>", "<Escape>"):
            self.assertIn(binding, method_source)
        self.assertNotIn('bind("<F8>"', method_source)
        self.assertIn("PDVEnterController(", method_source)
        controller_source = Path("controllers/pdv_enter_controller.py").read_text(encoding="utf-8")
        self.assertIn('"<Return>"', controller_source)
        self.assertIn('"<KP_Enter>"', controller_source)
        self.assertIn("será preservada", close_source)
        self.assertNotIn("self.carrinho_venda.clear()", close_source)


if __name__ == "__main__":
    unittest.main()
