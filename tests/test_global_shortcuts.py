import ast
from pathlib import Path
import unittest

from core.shortcut_manager import GLOBAL_SHORTCUTS, GlobalShortcutManager


class GlobalShortcutDefinitionsTests(unittest.TestCase):
    def test_atalhos_de_produtividade_estao_definidos(self):
        sequences = {item.sequence for item in GLOBAL_SHORTCUTS}
        self.assertTrue({
            "<Control-s>", "<Control-n>", "<Control-e>",
            "<Control-f>", "<Control-p>", "<F1>",
        }.issubset(sequences))

    def test_delete_nao_intercepta_campos_de_texto(self):
        class FakeEntry:
            def winfo_class(self):
                return "Entry"
        self.assertTrue(GlobalShortcutManager._is_text_input(FakeEntry()))


class AppShortcutIntegrationTests(unittest.TestCase):
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

    def test_app_instala_gerenciador_global(self):
        self.assertIn("_instalar_atalhos_globais", self.methods)
        source = ast.get_source_segment(
            self.source, self.methods["_instalar_atalhos_globais"]
        ) or ""
        self.assertIn("GlobalShortcutManager", source)
        for event in ("<<NabiClose>>", "<<NabiSearch>>", "<<NabiHelp>>", "<<NabiDelete>>"):
            self.assertIn(event, source)

    def test_fallbacks_principais_existem(self):
        for method in (
            "_atalho_fechar_janela_principal",
            "_atalho_pesquisar_tela_atual",
            "_atalho_excluir_tela_atual",
            "_atalho_ajuda_global",
        ):
            self.assertIn(method, self.methods)


if __name__ == "__main__":
    unittest.main()
