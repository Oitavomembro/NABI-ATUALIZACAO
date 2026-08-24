from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_configuracao_expoe_teste_fiscal_sem_valor_e_producao_bloqueada():
    block = SOURCE.split("def abrir_configuracao_fiscal", 1)[1].split("def abrir_central_fiscal", 1)[0]

    assert "TESTE FISCAL — HOMOLOGAÇÃO (SEM VALOR FISCAL)" in block
    assert "PRODUÇÃO FISCAL — BLOQUEADA NESTA VERSÃO" in block
    assert 'return environment_labels.get(environment.get(), "HOMOLOGACAO")' in block


def test_troca_de_ambiente_fiscal_exige_senha_mestra():
    block = SOURCE.split("def abrir_configuracao_fiscal", 1)[1].split("def abrir_central_fiscal", 1)[0]

    guard = block.index("if environment_changed and not self._confirmar_senha_gerencial(")
    save = block.index('"enabled": enabled.get(), "environment": chosen_environment')
    assert guard < save
    assert "O ambiente fiscal não foi alterado." in block


def test_pdv_identifica_homologacao_como_teste_sem_valor_fiscal():
    block = SOURCE.split("def abrir_pdv_independente", 1)[1].split("def _fechar_pdv", 1)[0]

    assert '"FISCAL TESTE — SEM VALOR FISCAL"' in block
    assert 'else "FISCAL PRODUÇÃO"' in block
