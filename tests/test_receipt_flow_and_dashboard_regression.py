from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class ReceiptFlowAndDashboardRegressionTests(unittest.TestCase):
    def _receipt_window_source(self):
        start = SOURCE.index("    def janela_recibo_pagamento_cliente")
        end = SOURCE.index("    def ajustar_texto_cupom", start)
        return SOURCE[start:end]

    def test_payment_receipt_does_not_generate_pdf_automatically(self):
        block = self._receipt_window_source()
        before_optional = block.split("def salvar_pdf_sob_demanda", 1)[0]
        self.assertNotIn("gerar_pdf_pagamento_cliente(", before_optional)
        self.assertIn("Salvar PDF (opcional)", block)

    def test_payment_receipt_primary_action_is_text_printing(self):
        block = self._receipt_window_source()
        self.assertIn("def imprimir_cupom():", block)
        self.assertIn("imprimir_texto_windows(", block)
        self.assertIn("Pré-visualização do cupom", block)

    def test_dashboard_activity_panel_is_removed(self):
        dashboard_start = SOURCE.index("    def tela_dashboard")
        dashboard_end = SOURCE.index("    def carregar_painel_atividades", dashboard_start)
        dashboard = SOURCE[dashboard_start:dashboard_end]
        self.assertNotIn("Painel de atividades", dashboard)
        self.assertNotIn("self.tabela_atividades =", dashboard)
        self.assertNotIn("_agendar_atualizacao_painel_atividades()", dashboard)
        self.assertIn("Histórico de Movimentações do Dia", dashboard)


if __name__ == "__main__":
    unittest.main()
