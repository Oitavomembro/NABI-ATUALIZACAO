from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_dashboard_separa_faturamento_de_recebimento_de_ficha():
    block = SOURCE.split("def tela_dashboard", 1)[1].split("def carregar_painel_atividades", 1)[0]
    assert "VENDAS REALIZADAS HOJE" in block
    assert "RECEBIMENTOS DE FICHAS HOJE" in block
    assert "não aumenta o faturamento" in block
    assert "Movimento Total" not in block


def test_central_fiscal_usa_cards_de_saidas_e_entradas_em_vez_de_status():
    block = SOURCE.split("def abrir_central_fiscal", 1)[1].split("def fazer_backup_config_agora", 1)[0]
    assert "SAÍDAS — VENDAS" in block
    assert "ENTRADAS — COMPRAS" in block
    assert "NFE_IMPORT_SERVICE.listar_importacoes()" in block
    assert "summary_labels" not in block
