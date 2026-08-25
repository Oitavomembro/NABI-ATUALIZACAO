from dataclasses import FrozenInstanceError

import pytest

from services.help_center_service import DiagnosticState, HelpCenterDiagnosticService


def test_catalogo_imutavel_checks_somente_leitura_e_ia_opcional(tmp_path):
    before = set(tmp_path.iterdir())
    service = HelpCenterDiagnosticService(
        persistent_dirs=[tmp_path], database_probe=lambda: {"state": "SAUDAVEL", "message": "integrity_check=ok"},
        backup_probe=lambda: {"state": "ALERTA", "message": "backup diário pendente"},
        printer_probe=lambda: {"state": "SAUDAVEL", "message": "1 disponível"}, nabi_probe=None,
    )
    results = service.run()
    assert len(results) == 6 and set(tmp_path.iterdir()) == before
    assert results[-1].state is DiagnosticState.INCONCLUSIVO
    with pytest.raises(FrozenInstanceError): results[0].message = "alterado"


def test_excecao_e_dados_sensiveis_falham_fechado(tmp_path):
    secret = "123.456.789-09 senha=segredo pessoa@empresa.com"
    def broken(): raise RuntimeError(secret)
    audit_rows = []
    service = HelpCenterDiagnosticService(
        persistent_dirs=[tmp_path], database_probe=broken,
        backup_probe=lambda: {"state": "SAUDAVEL", "message": secret},
        printer_probe=None, nabi_probe=None, audit=lambda *args: audit_rows.append(args),
    )
    rendered = repr(service.run()) + repr(audit_rows)
    assert "segredo" not in rendered and "123.456.789-09" not in rendered and "pessoa@empresa.com" not in rendered
    assert "RuntimeError" in rendered
