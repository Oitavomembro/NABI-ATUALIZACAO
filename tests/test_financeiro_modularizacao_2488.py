from decimal import Decimal
from pathlib import Path

from services.financeiro_calculator import FinanceiroCalculator
from services.financeiro_formatter import FinanceiroFormatter
from services.financeiro_view_data import FinanceiroViewData


def test_view_data_reutiliza_formatter_sem_formatacao_duplicada():
    assert issubclass(FinanceiroViewData, FinanceiroFormatter)
    fluxo = {"entradas": Decimal("10.00"), "saidas": Decimal("3.25"), "saldo": Decimal("6.75")}
    assert FinanceiroViewData.resumo_fluxo(fluxo) == FinanceiroFormatter.resumo_fluxo(fluxo)


def test_calculator_extrai_encargos_da_observacao_sem_float():
    assert FinanceiroCalculator.encargos_observacao(
        "Encargos aplicados: juros=1.25; multa=2.75"
    ) == Decimal("4.00")
    assert FinanceiroCalculator.encargos_observacao("sem encargos") == Decimal("0.00")


def test_service_financeiro_nao_contem_sql_direto():
    fonte = Path("services/financeiro_service.py").read_text(encoding="utf-8")
    marcadores = ("SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM ", ".execute(")
    assert not any(marcador in fonte for marcador in marcadores)


def test_view_data_nao_duplica_formatacao_monetaria():
    fonte = Path("services/financeiro_view_data.py").read_text(encoding="utf-8")
    assert "R$" not in fonte
    assert ".2f" not in fonte
