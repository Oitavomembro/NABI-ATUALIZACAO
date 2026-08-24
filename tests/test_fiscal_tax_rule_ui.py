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


def test_actor_tecnico_vem_da_sessao_e_nao_de_texto_da_gui():
    composition = SOURCE.split(
        "self.fiscal_tax_rule_service = FiscalTaxRuleService", 1
    )[1].split("self.fiscal_service.tax_rule_service", 1)[0]
    block = SOURCE.split("def abrir_regras_tributarias_bahia", 1)[1].split(
        "def abrir_central_fiscal", 1
    )[0]

    assert "actor_provider=self._ator_fiscal_autenticado" in composition
    assert "def _ator_fiscal_autenticado" in block
    assert "security.is_expired()" in block
    assert ".save(values, actor=" not in block
    assert ".deactivate(rule_id, actor=" not in block
