from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_central_fiscal_exibe_vendas_pendencias_e_reenvio():
    block = SOURCE.split("def abrir_central_fiscal", 1)[1].split("def fazer_backup_config_agora", 1)[0]
    assert "self.fiscal_sale_service.summary()" in block
    assert '"cancelled","Canceladas"' in block
    assert "self.fiscal_sale_service.list_sales()" in block
    assert 'text="Transmitir pendentes"' in block
    assert 'text="Reenviar selecionado"' in block
    assert "self.fiscal_service.retry_transmission" in block
    assert 'text="Cancelar autorizado"' in block
    assert "self.fiscal_sale_service.cancel_authorized" in block


def test_transmissao_fiscal_roda_fora_da_interface_e_nao_persiste_senha():
    block = SOURCE.split("def abrir_central_fiscal", 1)[1].split("def fazer_backup_config_agora", 1)[0]
    assert "TASK_MANAGER.submit" in block
    assert "process_transmission_queue" in block
    assert 'show="*"' in block
    assert 'password = ""' in block
    assert "salvar_config" not in block


def test_pdv_oferece_autorizacao_opcional_para_cartao_pos():
    block = SOURCE.split("def solicitar_pagamentos_pdv", 1)[1].split("def janela_pos_venda_comprovante", 1)[0]
    assert "Autorização da maquininha (opcional)" in block
    assert '"card_integration": 2' in block
    assert '"card_authorization"' in block
