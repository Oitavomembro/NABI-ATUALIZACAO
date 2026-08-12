from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
KEYBOARD = (ROOT / "ui" / "keyboard_navigation.py").read_text(encoding="utf-8")
SCHEMA = (ROOT / "database" / "schema_initializer.py").read_text(encoding="utf-8")


class V2494KeyboardLayoutCutterTests(unittest.TestCase):
    def test_clients_can_shrink_to_real_viewport(self):
        bloco = LEGACY.split('def tela_clientes(self, parent)', 1)[1].split('def carregar_clientes', 1)[0]
        self.assertIn('LayoutManager.configure_vertical_shell', bloco)
        self.assertIn('LayoutManager.apply_client_treeview', bloco)
        self.assertNotIn('content_width=1180, expand_to_viewport=True', bloco)

    def test_global_arrow_navigation_is_installed(self):
        self.assertIn('install_global_arrow_navigation(self)', LEGACY)
        self.assertIn('("<Right>", "<Down>")', KEYBOARD)
        self.assertIn('("<Left>", "<Up>")', KEYBOARD)

    def test_arrow_navigation_preserves_native_inputs_and_tables(self):
        for name in ('CTkEntry', 'CTkTextbox', 'CTkComboBox', 'Treeview', 'Listbox'):
            self.assertIn(f'"{name}"', KEYBOARD)

    def test_cutter_old_conflicting_default_is_removed(self):
        self.assertIn('(\"impressao_corte_automatico\", \"1\")', SCHEMA)
        self.assertNotIn('(\"impressao_corte_automatico\", \"0\")', SCHEMA)
        self.assertIn('migracao_corte_automatico_2494', SCHEMA)


if __name__ == '__main__':
    unittest.main()
