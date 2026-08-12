from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"nabicode_legacy.py").read_text(encoding="utf-8")
SVC=(ROOT/"services/pdv_transaction_service.py").read_text(encoding="utf-8")
class CreditTests(unittest.TestCase):
 def test_credit_ui_requests_installments_and_due_date(self):
  self.assertIn("Condições do crediário",UI); self.assertIn("Quantidade de parcelas",UI); self.assertIn("Primeiro vencimento",UI)
 def test_credit_service_creates_each_installment(self):
  self.assertIn("for installment_number in range(1, installment_count + 1)",SVC); self.assertIn("UPDATE movimentacoes SET total_parcelas",SVC)
 def test_receipt_uses_total_balance_and_internal_distribution(self):
  self.assertNotIn("Aplicar pagamento em",UI); self.assertIn("Pagamento aplicado ao saldo total",UI); self.assertIn('{"tipo": "AUTO", "limite": saldo}',UI)
if __name__=="__main__": unittest.main()
