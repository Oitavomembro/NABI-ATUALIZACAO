import ast
from pathlib import Path
import unittest

from core.window_actions import WindowActionController, WindowActionRegistration


class WindowActionUnitTests(unittest.TestCase):
    def test_resultado_false_impede_fluxo_de_fechamento(self):
        self.assertFalse(WindowActionController._action_succeeded(False))
        self.assertTrue(WindowActionController._action_succeeded(None))
        self.assertTrue(WindowActionController._action_succeeded(True))

    def test_registration_defaults_are_safe(self):
        registration = WindowActionRegistration()
        self.assertTrue(registration.confirm_delete)
        self.assertTrue(registration.confirm_close)
        self.assertIsNone(registration.save)


class WindowActionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path('nabicode_legacy.py').read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        cls.app = next(node for node in cls.tree.body if isinstance(node, ast.ClassDef) and node.name == 'FicharioMoveisApp')
        cls.methods = {node.name: node for node in cls.app.body if isinstance(node, ast.FunctionDef)}

    def test_controller_is_installed(self):
        method = ast.get_source_segment(self.source, self.methods['_instalar_atalhos_globais']) or ''
        self.assertIn('WindowActionController', method)
        self.assertIn('<<NabiSave>>', method)

    def test_product_xml_and_pdv_register_universal_actions(self):
        for method_name in ('abrir_cadastro_produto', 'abrir_importacao_xml', 'abrir_pdv_independente'):
            method = ast.get_source_segment(self.source, self.methods[method_name]) or ''
            self.assertIn('self.window_actions.register', method)

    def test_main_new_and_edit_fallbacks_exist(self):
        self.assertIn('_atalho_novo_tela_atual', self.methods)
        self.assertIn('_atalho_editar_tela_atual', self.methods)
        self.assertIn('_atalho_salvar_tela_atual', self.methods)


if __name__ == '__main__':
    unittest.main()
