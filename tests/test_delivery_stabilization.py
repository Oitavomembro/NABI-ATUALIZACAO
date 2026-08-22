from pathlib import Path


SOURCE = Path("nabicode_legacy.py").read_text(encoding="utf-8")


def _method(name: str, next_name: str) -> str:
    start = SOURCE.index(f"    def {name}")
    end = SOURCE.index(f"    def {next_name}", start)
    return SOURCE[start:end]


def test_edicao_de_cliente_usa_servico_sem_sql_direto():
    block = _method("editar_cliente_selecionado", "editar_perfil_fiscal_cliente")
    assert "CUSTOMER_REGISTRATION_SERVICE.editar(" in block
    assert "UPDATE clientes SET numero_ficha" not in block


def test_pdv_consumiu_carrinho_antes_dos_efeitos_secundarios():
    block = _method("finalizar_venda", "tela_clientes")
    consume = block.index("consume_committed_cart(")
    receipt = block.index("janela_venda_finalizada(")
    assert consume < receipt
    assert "erro_historico is not None" in block
    assert "A venda foi registrada com sucesso e o carrinho foi encerrado" in block
