from pathlib import Path

from services.nabimig_import_service import NabiMigImportPreview, NabiMigImportResult
from services.nabimig_ui_service import final_report_text, preview_text


ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_existing_phase2_and_nabimig_share_the_migration_tab():
    assert 'aba = abas.tab("Migração")' in LEGACY
    assert "Preparar Fase 2" in LEGACY
    assert "Importar Fase 2" in LEGACY
    assert "IMPORTAR PACOTE DO CONVERSOR NABICODE (.nabimig)" in LEGACY
    assert "NabiMigImportService()" in LEGACY
    assert 'placeholder_text="Selecione um arquivo .sql ou .nabimig"' in LEGACY
    assert 'text="1. Analisar"' in LEGACY
    assert 'text="2. Preparar"' in LEGACY
    assert 'text="3. Migrar"' in LEGACY
    assert "validar_nabimig_ui(False) if arquivo_nabimig_selecionado()" in LEGACY
    assert "validar_nabimig_ui(True) if arquivo_nabimig_selecionado()" in LEGACY


def test_report_is_technical_and_contains_required_audit_fields():
    preview = NabiMigImportPreview(
        package="C:/temp/pacote.nabimig", package_sha256="abc", source_system="HOST_FIREBIRD_2_5",
        source_sha256="def", counts={"customers": 2}, warnings=("1 fornecedor sem nome",), errors=(),
    )
    result = NabiMigImportResult(
        backup="C:/temp/backup.db", inserted={"customers": 2}, updated={}, package_sha256="abc",
        selected_categories=("customers",), demo_customers_removed=3, open_balance=10171.0,
    )
    report = final_report_text(preview, result, "C:/temp/destino.db", demos_requested_for_removal=True)
    assert "Status: SUCESSO" in report
    assert "HOST_FIREBIRD_2_5" in report
    assert "Backup: C:/temp/backup.db" in report
    assert "Saldo aberto importado: R$ 10.171,00" in report
    assert "Verificação de chaves estrangeiras: OK" in report
    assert "documento" not in report.lower()
    assert "telefone" not in report.lower()
    assert "Clientes: 2" in preview_text(preview)
