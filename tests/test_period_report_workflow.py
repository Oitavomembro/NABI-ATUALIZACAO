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
    assert "Gráfico / Dashboard" not in block
    assert "Indicadores" not in block
    assert 'text="Imprimir"' not in block
    assert "Agendar relatório" in block
    assert "_relatorios_rotulo_id" in block


def test_central_fiscal_mostra_escolhas_antes_da_grade():
    block = SOURCE.split("def abrir_central_fiscal", 1)[1].split("def fazer_backup_config_agora", 1)[0]
    assert 'action_panel.pack(fill="x", padx=12, pady=(0, 10), before=tree)' in block
    assert "O que você deseja fazer?" in block
    assert 'text="Ver saídas"' in block
    assert 'text="Ver entradas"' in block
    assert 'text="Ver todos os documentos"' not in block
    assert "filters.pack_forget()" in block
    assert "tree.pack_forget()" in block
    assert 'tree.pack(fill="both", expand=True, padx=(12, 28), pady=(0, 24), after=action_panel)' in block
    assert 'view_mode["value"] in {"ENTRADAS", "TODOS"}' in block
    assert '["Todas as saídas", "Vendas fiscais", "Vendas não fiscais", "Orçamentos"]' in block
    assert '["Todas as entradas", "Entradas fiscais (NF-e/DF-e)", "Entradas não fiscais", "Recebimentos de fichas"]' in block
    assert 'self.pdv_transaction_service.list_sales_for_period(' in block
    assert "period.pack_forget()" in block
    assert "open_date_picker" in block
    assert 'text="Mostrar resultados"' in block
    assert "def apply_document_filters" in block
    assert "def hide_document_results" in block
    assert 'period.pack(fill="x", padx=12, pady=(2, 4), before=action_panel)' in block
    assert 'period.pack(fill="x", padx=12, pady=(2, 4), before=filters)' not in block
    assert 'command=lambda _value: hide_document_results()' in block
    assert "select_period_date(start_var, value)" in block
    assert "select_period_date(end_var, value)" in block
    assert '"FISCAL" if is_fiscal else "NÃO FISCAL"' in block
    assert 'REPORT_SERVICE.generate(\n                        "recebimentos"' in block


def test_recebimentos_sao_relatorio_separado_de_vendas():
    assert ReportService.REPORTS["recebimentos"] == "Recebimentos de fichas por período"
