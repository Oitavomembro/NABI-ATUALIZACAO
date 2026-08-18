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
    password_helper = SOURCE.split("def _obter_senha_certificado", 1)[1].split("def abrir_configuracao_fiscal", 1)[0]
    assert "TASK_MANAGER.submit" in block
    assert "process_transmission_queue" in block
    assert "self._obter_senha_certificado" in block
    assert 'show="*"' in password_helper
    assert "session_certificate_password" in password_helper
    assert 'password = ""' in block
    assert "salvar_config" not in block


def test_pdv_oferece_autorizacao_opcional_para_cartao_pos():
    block = SOURCE.split("def solicitar_pagamentos_pdv", 1)[1].split("def janela_pos_venda_comprovante", 1)[0]
    assert "Autorização da maquininha (opcional)" in block
    assert '"card_integration": 2' in block
    assert '"card_authorization"' in block


def test_configuracao_fiscal_oferece_auditoria_unica_do_catalogo():
    block = SOURCE.split("def abrir_configuracao_fiscal", 1)[1].split("def abrir_central_fiscal", 1)[0]
    assert "self.fiscal_catalog_readiness_service.audit" in block
    assert 'text="Verificar catálogo fiscal"' in block
    assert "report.issues[:12]" in block
    assert 'aba_inicial="Fiscal"' in block
    assert "ao_salvar=self.abrir_configuracao_fiscal" in block
    assert "self.fiscal_preflight_service.run" in block
    assert 'text="Executar pré-voo fiscal local"' in block
    assert "Modelos aprovados:" in block
    assert "result.xml_sha256_by_model" in block
    assert "Preencher usando uma NF-e/NFC-e antiga da empresa" in block
    assert 'fields["sale_series_55"]' in block
    assert 'fields["sale_series_65"]' in block
    assert 'fields["issuer_im"]' in block
    assert "Nenhum documento foi transmitido" in block
    assert 'text="Visualizar metadados"' in block
    assert 'text="Remover certificado"' in block
    assert "install_certificate_securely" in block
    assert "remove_managed_certificate" in block
    assert 'text="Testar conexão com a SEFAZ"' in block
    assert "check_service_status" in block
    assert "TASK_MANAGER.submit" in block
    assert 'text="Configurar próximo número fiscal"' in block
    assert "initialize_numbering" in block
    assert "INICIAR_NUMERACAO_FISCAL" in block


def test_central_fiscal_expoe_eventos_e_download_sem_rotas_paralelas():
    block = SOURCE.split("def abrir_central_fiscal", 1)[1].split("def fazer_backup_config_agora", 1)[0]
    assert 'text="Baixar XML"' in block
    assert 'text="Enviar CC-e"' in block
    assert 'text="Inutilizar numeração"' in block
    assert "self.fiscal_service.send_event" in block
    assert "self.fiscal_service.inutilize_numbers" in block


def test_cadastro_oficial_de_produto_aceita_correcao_fiscal_assistida():
    block = SOURCE.split("def abrir_cadastro_produto", 1)[1].split("def editar_produto_selecionado", 1)[0]
    assert "aba_inicial=None" in block
    assert "abas_produto.set(aba_inicial)" in block
    assert "if callable(ao_salvar)" in block
    assert "e_ibs_class.get()" in block
