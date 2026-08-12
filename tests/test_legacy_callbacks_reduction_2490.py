import ast
from pathlib import Path

SOURCE = Path("nabicode_legacy.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
APP = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")
METHODS = {node.name: node for node in APP.body if isinstance(node, ast.FunctionDef)}


def block(name):
    node = METHODS[name]
    return "\n".join(SOURCE.splitlines()[node.lineno - 1: node.end_lineno])


def test_finance_callbacks_are_thin_legacy_adapters():
    names = [
        "carregar_financeiro", "_titulo_financeiro_selecionado", "novo_titulo_financeiro",
        "baixar_titulo_financeiro", "definir_centro_custo_financeiro", "abrir_recorrencias_financeiro",
        "conciliar_pagamento_financeiro", "cancelar_titulo_financeiro", "abrir_conciliacoes_financeiro",
        "abrir_relatorio_centros_custo", "abrir_detalhes_financeiros", "estornar_pagamento_financeiro",
    ]
    for name in names:
        body = block(name)
        assert "_financeiro_callbacks()" in body
        assert "FINANCEIRO_SERVICE." not in body
        assert len(body.splitlines()) <= 3


def test_pdv_window_has_no_competing_global_return_binding():
    pdv = block("abrir_pdv_independente")
    assert 'win.bind("<Return>"' not in pdv
    assert "PDVEnterController(" in pdv
    assert "install_enter_navigation(" not in pdv


def test_legacy_enter_signature_is_preserved_as_adapter():
    body = block("_enter_contexto_pdv")
    assert "event=None" in body
    assert "dispatch_legacy_event(event)" in body
    assert len(body.splitlines()) <= 6


def test_duplicate_barcode_selector_was_removed():
    defs = [node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name == "_selecionar_produto_por_codigo_barras"]
    assert len(defs) == 1
