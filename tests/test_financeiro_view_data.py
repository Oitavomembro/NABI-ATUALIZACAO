from decimal import Decimal
import unittest

from services.financeiro_view_data import FinanceiroViewData


class FinanceiroViewDataTests(unittest.TestCase):
    def test_resumos_preservam_texto_legado(self):
        fluxo = {"entradas": Decimal("10"), "saidas": Decimal("3.50"), "saldo": Decimal("6.50")}
        dre = {"resultado_competencia": Decimal("7"), "resultado_realizado": Decimal("6.50")}
        self.assertEqual(FinanceiroViewData.resumo_fluxo(fluxo), "Fluxo: entradas R$ 10.00 | saídas R$ 3.50 | saldo R$ 6.50")
        self.assertEqual(FinanceiroViewData.resumo_dre(dre), "DRE: competência R$ 7.00 | realizado R$ 6.50")

    def test_linha_titulo_preserva_ordem_e_formatacao(self):
        titulo = {
            "id": 4, "tipo": "RECEBER", "pessoa_nome": "Ana", "descricao": "Parcela",
            "data_vencimento": "2026-08-10", "valor_original": Decimal("100"),
            "valor_pago": Decimal("25.5"), "saldo_aberto": Decimal("74.5"), "status": "PARCIAL",
        }
        self.assertEqual(
            FinanceiroViewData.linha_titulo(titulo, "Vendas"),
            (4, "RECEBER", "Ana", "Parcela", "2026-08-10", "R$ 100.00", "R$ 25.50", "R$ 74.50", "PARCIAL", "Vendas"),
        )

    def test_textos_de_selecao_preservam_formato(self):
        pagamentos = [{"id": 8, "data_pagamento": "2026-08-06", "valor": Decimal("15")}]
        self.assertEqual(FinanceiroViewData.pagamentos_para_selecao(pagamentos), "8 - 2026-08-06 - R$ 15.00")
        conciliacoes = [{"id": 8, "data_pagamento": "2026-08-06", "valor": Decimal("15"), "conciliado": True, "conciliacao": {"referencia": "PIX-1"}}]
        self.assertEqual(FinanceiroViewData.conciliacoes_para_selecao(conciliacoes), "8 | 2026-08-06 | R$ 15.00 | CONCILIADO: PIX-1")

    def test_detalhes_vazios_preservam_mensagens(self):
        texto = FinanceiroViewData.detalhes_financeiros({"movimentos": []}, {"titulos_competencia": []})
        self.assertEqual(texto, "MOVIMENTOS REALIZADOS\nSem movimentos realizados.\n\nTÍTULOS POR COMPETÊNCIA\nSem títulos por competência.")


if __name__ == "__main__":
    unittest.main()
