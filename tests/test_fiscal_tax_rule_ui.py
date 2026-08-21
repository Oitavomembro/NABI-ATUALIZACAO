from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_configuracao_expoe_matriz_tributaria_da_bahia():
    config = SOURCE.split("def abrir_configuracao_fiscal", 1)[1].split(
        "def abrir_regras_tributarias_bahia", 1
    )[0]
    assert 'text="Regras tributárias da Bahia"' in config
    assert "command=self.abrir_regras_tributarias_bahia" in config


def test_matriz_nao_inventa_aliquota_e_exige_senha_para_alterar():
    block = SOURCE.split("def abrir_regras_tributarias_bahia", 1)[1].split(
        "def abrir_central_fiscal", 1
    )[0]
    assert "nunca inventa alíquota" in block
    assert "self.fiscal_tax_rule_service.list_rules()" in block
    assert "self.fiscal_tax_rule_service.save(values)" in block
    assert "self.fiscal_tax_rule_service.deactivate(rule_id)" in block
    assert block.count("self._confirmar_senha_mestra(") == 2
    assert "Responsável contábil que aprovou" in block
    assert "Código de benefício fiscal aprovado (8 ou 10 caracteres" in block
    assert 'f"cBenef {rule.benefit_code or \'-\'}' in block
    assert "Produção continua bloqueada" in block
