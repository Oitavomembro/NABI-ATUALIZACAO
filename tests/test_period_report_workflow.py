from pathlib import Path

from services.report_service import ReportService


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_relatorios_expoem_calculo_totais_e_pdf_de_forma_clara():
    block = SOURCE.split("def tela_relatorios", 1)[1].split("def _gerar_relatorio_por_enter", 1)[0]
    assert "Data inicial DD/MM/AAAA" in block
    assert "Data final DD/MM/AAAA" in block
    assert "Calcular e listar" in block
    assert "REGISTROS NO PERÍODO" in block
    assert "VALOR TOTAL DO PERÍODO" in block
    assert "Gerar arquivo PDF" in block


def test_central_fiscal_abre_relatorio_por_periodo():
    block = SOURCE.split("def abrir_central_fiscal", 1)[1].split("def fazer_backup_config_agora", 1)[0]
    assert "Relatório por período / PDF" in block
    assert 'self.mostrar_tela("relatorios")' in block


def test_recebimentos_sao_relatorio_separado_de_vendas():
    assert ReportService.REPORTS["recebimentos"] == "Recebimentos de fichas por período"
