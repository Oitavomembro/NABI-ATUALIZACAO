from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_produtos_expoe_cadastro_via_xml_em_qualquer_modo():
    block = SOURCE.split("def tela_produtos", 1)[1].split("def carregar_produtos", 1)[0]
    button = 'text="📄 Cadastrar produtos via XML"'

    assert block.count(button) == 1
    assert block.index(button) < block.index("if modo_fiscal_ativo():")
    assert "command=self.abrir_importacao_xml" in block


def test_pesquisa_global_nao_trata_cadastro_via_xml_como_exclusivo_fiscal():
    block = SOURCE.split("def _comandos_pesquisa_global", 1)[1].split("def abrir_pesquisa_global", 1)[0]

    assert 'CommandDefinition("import_xml", "Cadastrar produtos via XML"' in block
    fiscal_line = next(line for line in block.splitlines() if "comandos_fiscais =" in line)
    assert '"import_xml"' not in fiscal_line
