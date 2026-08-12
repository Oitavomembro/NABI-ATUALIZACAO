from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
UI=(R/'nabicode_legacy.py').read_text(encoding='utf-8')
PDV=(R/'services/pdv_service.py').read_text(encoding='utf-8')
TX=(R/'services/pdv_transaction_service.py').read_text(encoding='utf-8')
REC=(R/'services/receipt_service.py').read_text(encoding='utf-8')
class T(unittest.TestCase):
 def test_modal(self):
  self.assertIn('Fiado — paga tudo',UI); self.assertIn('Entrada + parcelas',UI)
 def test_entry_credit(self):
  self.assertIn('entrada somada ao valor financiado',PDV); self.assertIn('financed_value',TX)
 def test_cupom(self):
  self.assertIn('Compra a prazo',REC); self.assertIn('PAGA NESTE RECEBIMENTO',REC)
 def test_login_disabled(self):
  i=UI.index('    def abrir_login_usuario'); self.assertIn('return None',UI[i:i+120])
if __name__=='__main__': unittest.main()
