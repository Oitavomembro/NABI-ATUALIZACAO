from pathlib import Path
import unittest
S=(Path(__file__).resolve().parents[1]/"nabicode_legacy.py").read_text(encoding="utf-8")
class PDVCleanLayoutTests(unittest.TestCase):
 def test_top_menu_contains_secondary_actions(self):
  start=S.index("    def abrir_pdv_independente")
  end=S.index("    def _enter_contexto_pdv",start)
  opening=S[start:end]
  self.assertIn("Vendas do dia  [F7]",opening)
  self.assertIn("ORÇAMENTO DESLIGADO  [F5]",opening)
  for label in ("Cliente rápido", "Pré-venda [F8]", "Documentos", "Cancelar venda"):
   self.assertNotIn(f'text="{label}',opening)
 def test_side_panel_keeps_finalize_visible(self):
  self.assertIn("FINALIZAR VENDA  [F9]",S)
  self.assertNotIn("botoes_pdv = (",S)
 def test_double_click_edits_item_and_removal_is_explicit(self):
     self.assertIn('"<Double-Button-1>"',S)
     self.assertIn("self.abrir_editor_item_carrinho",S)
     self.assertIn("Duplo clique: editar item da venda",S)
     self.assertIn('menu.add_command(label="Remover item"',S)
if __name__=="__main__": unittest.main()
