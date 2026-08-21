from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / "docs" / name).read_text(encoding="utf-8")


def test_commercial_scope_keeps_non_fiscal_login_optional_and_fiscal_blocked():
    document = _read("LIBERACAO_COMERCIAL_GESTAO.md")
    assert "login não é obrigatório" in document
    assert "emissão fiscal de produção permanece bloqueada" in document
    assert "senha mestra" in document


def test_release_gate_requires_backup_restore_and_clean_test_data():
    document = _read("LIBERACAO_COMERCIAL_GESTAO.md")
    assert "backup criado" in document
    assert "banco temporário" in document
    assert "Nenhuma credencial, certificado, banco real" in document


def test_customer_documents_cover_privacy_support_and_incidents():
    privacy = _read("POLITICA_DE_PRIVACIDADE_MODELO.md")
    terms = _read("TERMOS_DE_LICENCA_MODELO.md")
    incident = _read("RESPOSTA_A_INCIDENTES.md")
    assert "Dados tratados" in privacy
    assert "Direitos e solicitações" in privacy
    assert "Atualizações e suporte" in terms
    assert "acesso remoto silencioso" in terms
    assert "Preservar banco, logs e backups" in incident
    assert "causa raiz" in incident
