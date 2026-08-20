from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")
BLOCK = SOURCE.split("def abrir_importacao_xml", 1)[1].split("def abrir_pdv_independente", 1)[0]


def test_quantidade_do_xml_e_somente_leitura_e_fator_recalcula_custo():
    assert "Recebido no XML:" in BLOCK
    assert "(somente leitura)" in BLOCK
    assert 'campo_editor(aba_estoque, "Quantidade recebida"' not in BLOCK
    assert '"custo_embalagem": float(item.valor_unitario)' in BLOCK
    assert 'float(configuracoes[indice]["custo_embalagem"]) / fator' in BLOCK
    assert 'fator_var.trace_add("write", lambda *_: atualizar_calculo("fator"))' in BLOCK


def test_lista_compacta_e_salvamento_sequencial_ficam_fora_da_rolagem():
    assert 'colunas = ("Codigo", "Descricao", "Recebido", "Entrada", "Custo", "Venda", "Status")' in BLOCK
    assert 'text="Colar valores do Excel"' not in BLOCK
    assert 'text="Salvar item e atualizar lista"' not in BLOCK
    footer = BLOCK.split("rodape = ctk.CTkFrame(win", 1)[1]
    assert 'text="Salvar produto e ir para o próximo"' in footer
    assert "command=confirmar_item_e_avancar" in footer


def test_unidades_comerciais_basicas_estao_disponiveis_sem_cadastro_previo():
    for unit in ("UN", "CX", "PCT", "FD", "KG", "G", "L", "ML", "M", "M2", "M3"):
        assert f'"{unit}"' in BLOCK


def test_barra_principal_abre_central_fiscal_no_lugar_de_compras():
    header = SOURCE.split("def criar_cabecalho_e_botoes", 1)[1].split(
        "def _chave_usuario_preferencias", 1
    )[0]
    assert 'text="🧾 Central Fiscal"' in header
    assert "btn_compras.configure(command=self.abrir_central_fiscal)" in header
    assert 'text="📥 Compras"' not in header
