from decimal import Decimal
from pathlib import Path

from helpers.legacy_reduction_helpers import (
    mysql_migration_report_text,
    parse_nonnegative_number,
)


SOURCE = Path(__file__).resolve().parents[1].joinpath("nabicode_legacy.py").read_text(encoding="utf-8")


def _method_block(name: str, next_name: str) -> str:
    start = SOURCE.index(f"    def {name}")
    end = SOURCE.index(f"    def {next_name}", start)
    return SOURCE[start:end]


def test_xml_conference_uses_the_shared_validated_number_parser():
    block = SOURCE[SOURCE.index("        def salvar_item_atual"):SOURCE.index("        candidatos_rotulo_id")]
    assert "numero(" not in block
    assert block.count("parse_nonnegative_number(") == 4
    assert "greater_than_zero=True" in block
    assert parse_nonnegative_number("1,25", "Quantidade", greater_than_zero=True) == 1.25


def test_invalid_product_price_fallback_has_decimal_available():
    block = _method_block("_preencher_sugestoes_produto", "exibir_sugestoes_produto")
    assert "from decimal import Decimal" in SOURCE[:1000]
    assert 'preco = Decimal("0")' in block
    assert Decimal("0") == 0


def test_report_dashboard_uses_the_value_returned_by_indicators():
    block = _method_block("abrir_dashboard_relatorios", "_executar_agendamentos_relatorios")
    assert "indicadores = REPORT_SERVICE.indicators(" in block
    assert "indicators[" not in block
    for key in ("vendas_total", "receber_aberto", "pagar_aberto", "estoque_baixo"):
        assert f"indicadores['{key}']" in block


def test_migration_report_save_uses_the_same_formatter_as_preview():
    marker = "        def salvar_relatorio_mig():"
    start = SOURCE.index(marker)
    end = SOURCE.index("        def preparar_fase2_ui():", start)
    block = SOURCE[start:end]
    assert "formatar_relatorio(" not in block
    assert "mysql_migration_report_text(self.ultimo_relatorio_migracao)" in block

    report = {
        "arquivo": "backup.sql",
        "tamanho": 0,
        "tabelas": [],
        "contagens": {},
        "clientes": 0,
        "duplicados_cpf": 0,
        "duplicados_ficha": 0,
        "duplicados_codigo": 0,
        "sem_nome": 0,
        "datas_invalidas": 0,
        "telefones_invalidos": 0,
    }
    assert "STATUS: SIMULAÇÃO CONCLUÍDA" in mysql_migration_report_text(report)
