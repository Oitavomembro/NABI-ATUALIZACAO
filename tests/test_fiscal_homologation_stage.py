from pathlib import Path

from services.fiscal_service import FiscalService


ROOT = Path(__file__).resolve().parents[1]


def test_homologation_identity_uses_official_recipient_without_real_customer_data():
    assert FiscalService.HOMOLOGATION_RECIPIENT_CNPJ == "99999999000191"
    assert FiscalService.HOMOLOGATION_RECIPIENT_NAME == (
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    )


def test_stage_two_checklist_keeps_production_blocked_and_requires_evidence():
    document = (ROOT / "docs" / "HOMOLOGACAO_FISCAL_BAHIA.md").read_text(
        encoding="utf-8"
    )
    assert "producao\ncontinua bloqueada" in document
    assert "nao executar teste online sem acompanhamento" in document
    assert "codigo e mensagem de cada retorno" in document
    assert "nao versionar certificado, senha, XML real ou banco" in document
