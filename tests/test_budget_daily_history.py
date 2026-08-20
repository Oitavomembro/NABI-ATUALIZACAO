from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")
VALIDATOR_SOURCE = (Path(__file__).resolve().parents[1] / "validators" / "receipt_validator.py").read_text(encoding="utf-8")


def test_orcamento_e_tipo_de_documento_aceito_pelo_comprovante():
    assert '"ORCAMENTO": "ORCAMENTO"' in VALIDATOR_SOURCE
    assert '"VENDA", "ENTREGA", "ORCAMENTO"' in VALIDATOR_SOURCE


def test_conclusao_do_orcamento_abre_previsualizacao_sem_impressao_automatica():
    block = SOURCE.split("def concluir_acao_pdv", 1)[1].split("def abrir_vendas_do_dia_pdv", 1)[0]
    assert 'self.salvar_documento_pdv("ORCAMENTO")' in block
    assert "self._visualizar_orcamento_pdv(documento)" in block
    assert 'titulo="Orçamento salvo"' in block
    assert "janela_preview_documento" in block
    assert "imprimir_texto_windows" not in block


def test_vendas_do_dia_lista_orcamentos_separados_das_vendas():
    block = SOURCE.split("def abrir_vendas_do_dia_pdv", 1)[1].split("def abrir_vendas_suspensas", 1)[0]
    assert 'self.pdv_service.listar_documentos("ORCAMENTO")' in block
    assert '"ORÇAMENTO"' in block
    assert '"SEM VALOR FISCAL"' in block
    assert 'table.tag_configure("orcamento"' in block
    assert 'row.get("record_type") == "ORCAMENTO"' in block
