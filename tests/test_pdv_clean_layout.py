from pathlib import Path
import unittest
S=(Path(__file__).resolve().parents[1]/"nabicode_legacy.py").read_text(encoding="utf-8")
class PDVCleanLayoutTests(unittest.TestCase):
 def test_top_menu_contains_secondary_actions(self):
  self.assertIn("comandos_menu_pdv = (",S)
  for label in ("Reabrir [F7]","Cliente rápido","Documentos","Pré-venda [F8]"):
   self.assertIn(label,S)
 def test_side_panel_keeps_finalize_visible(self):
  self.assertIn("FINALIZAR VENDA  [F9]",S)
  self.assertNotIn("botoes_pdv = (",S)
 def test_double_click_edits_item_and_removal_is_explicit(self):
     self.assertIn('"<Double-Button-1>"',S)
     self.assertIn("self.abrir_editor_item_carrinho",S)
     self.assertIn("Duplo clique: editar item da venda",S)
     self.assertIn('menu.add_command(label="Remover item"',S)
if __name__=="__main__": unittest.main()
