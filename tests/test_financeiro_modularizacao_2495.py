from decimal import Decimal

from services.financeiro_calculator import FinanceiroCalculator


def test_fluxo_caixa_centraliza_classificacao_e_ignora_movimento_do_financeiro():
    pagamentos = [
        {"tipo": "RECEBER", "valor": "10.25", "id": 1},
        {"tipo": "PAGAR", "valor": "2.10", "id": 2},
    ]
    movimentos = [
        {"tipo": "VENDA", "valor": "7.65", "status_pagamento": "PAGO", "origem_sistema": ""},
        {"tipo": "DESPESA", "valor": "1.20", "status_pagamento": "QUITADO", "origem_sistema": ""},
        {"tipo": "VENDA", "valor": "99.00", "status_pagamento": "PAGO", "origem_sistema": "FINANCEIRO"},
        {"tipo": "VENDA", "valor": "50.00", "status_pagamento": "ABERTO", "origem_sistema": ""},
    ]

    resultado = FinanceiroCalculator.fluxo_caixa(pagamentos, movimentos)

    assert resultado["entradas"] == Decimal("17.90")
    assert resultado["saidas"] == Decimal("3.30")
    assert resultado["saldo"] == Decimal("14.60")
    assert len(resultado["movimentos"]) == 4


def test_dre_reutiliza_mesma_classificacao_do_fluxo_e_preserva_decimal():
    titulos = [
        {"tipo": "RECEBER", "valor_original": "100.10"},
        {"tipo": "PAGAR", "valor_original": "40.05"},
    ]
    pagamentos = [
        {"tipo": "RECEBER", "valor": "30.03"},
        {"tipo": "PAGAR", "valor": "10.01"},
    ]
    movimentos = [
        {"tipo": "VENDA", "valor": "20.02", "status_pagamento": "PAGO", "origem_sistema": ""},
        {"tipo": "DESPESA", "valor": "5.05", "status_pagamento": "ABERTO", "origem_sistema": ""},
        {"tipo": "VENDA", "valor": "500", "status_pagamento": "PAGO", "origem_sistema": "TITULO_FINANCEIRO"},
    ]

    resultado = FinanceiroCalculator.dre(titulos, pagamentos, movimentos)

    assert resultado == {
        "receitas_competencia": Decimal("120.12"),
        "despesas_competencia": Decimal("45.10"),
        "resultado_competencia": Decimal("75.02"),
        "receitas_realizadas": Decimal("50.05"),
        "despesas_realizadas": Decimal("10.01"),
        "resultado_realizado": Decimal("40.04"),
    }


def test_natureza_movimento_legado_tem_uma_unica_regra_para_fluxo_e_dre():
    assert FinanceiroCalculator.natureza_movimento_legado({"tipo": "recebimento"}) == "ENTRADA"
    assert FinanceiroCalculator.natureza_movimento_legado({"tipo": "despesa"}) == "SAIDA"
    assert FinanceiroCalculator.natureza_movimento_legado({"tipo": "ajuste"}) is None
    assert FinanceiroCalculator.natureza_movimento_legado(
        {"tipo": "VENDA", "origem_sistema": "financeiro"}
    ) is None
