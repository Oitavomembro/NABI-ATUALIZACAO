import ast
import unittest
from pathlib import Path


class ScrollGlobalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("nabicode_legacy.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.functions = {
            node.name: ast.get_source_segment(cls.source, node) or ""
            for node in ast.walk(cls.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_main_content_screens_use_expected_scroll_strategy(self):
        for name in ("tela_vendas", "tela_financeiro", "tela_configs"):
            with self.subTest(screen=name):
                self.assertIn("BidirectionalScrollableFrame", self.functions[name])
        clientes = self.functions["tela_clientes"]
        self.assertNotIn("BidirectionalScrollableFrame", clientes)
        self.assertIn("LayoutManager.configure_vertical_shell", clientes)
        self.assertIn("LayoutManager.apply_client_treeview", clientes)

    def test_finance_and_cart_tables_have_both_scrollbars(self):
        vendas = self.functions["tela_vendas"]
        financeiro = self.functions["tela_financeiro"]
        self.assertIn("xscrollcommand", vendas)
        self.assertIn("yscrollcommand", vendas)
        self.assertIn("orient=\"horizontal\"", vendas)
        self.assertIn("xscrollcommand", financeiro)
        self.assertIn("yscrollcommand", financeiro)
        self.assertIn("orient=\"horizontal\"", financeiro)

    def test_mouse_wheel_binding_is_persistent_and_filtered_by_ancestry(self):
        cls = next(
            node for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "BidirectionalScrollableFrame"
        )
        class_source = ast.get_source_segment(self.source, cls) or ""
        self.assertIn("self._bind_wheel()", class_source)
        self.assertIn("def _event_is_inside", class_source)
        self.assertIn("if not self._event_is_inside(event)", class_source)
        self.assertNotIn('self.bind("<Leave>", self._unbind_wheel', class_source)

    def test_headers_and_footers_remain_outside_expandable_content(self):
        for name in ("tela_vendas", "tela_financeiro", "tela_configs"):
            body = self.functions[name]
            header = body.index("criar_cabecalho_e_botoes")
            scroll = body.index("BidirectionalScrollableFrame")
            self.assertLess(header, scroll)
            self.assertIn("adicionar_rodape_status", body[:scroll])

        clientes = self.functions["tela_clientes"]
        header = clientes.index("criar_cabecalho_e_botoes")
        content = clientes.index("conteudo_cli = ctk.CTkFrame")
        footer = clientes.rindex("adicionar_rodape_status")
        self.assertLess(header, content)
        self.assertGreater(footer, content)


if __name__ == "__main__":
    unittest.main()
