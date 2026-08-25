from dataclasses import FrozenInstanceError
from datetime import datetime
import json

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


def test_relatorio_sanitizado_cobre_catalogo_e_grava_atomicamente(tmp_path, monkeypatch):
    secret = "senha=segredo 123.456.789-09 pessoa@empresa.com C:\\Users\\pessoa\\dados"
    service = HelpCenterDiagnosticService(
        persistent_dirs=[tmp_path], database_probe=lambda: {"state":"SAUDAVEL", "message":secret},
        backup_probe=None, printer_probe=None, nabi_probe=None,
        clock=lambda: datetime(2026, 8, 24, 15, 30, 0),
    )
    results = service.run(); replacements = []
    import services.help_center_service as module
    original = module.os.replace
    monkeypatch.setattr(module.os, "replace", lambda source, target: (replacements.append((source, target)), original(source, target))[1])
    path = service.save_report(tmp_path / "socorro.json", results)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rendered = path.read_text(encoding="utf-8")
    assert payload["schema"] == "nabicode.help-center-report.v1"
    assert len(payload["results"]) == 6 and replacements
    assert "segredo" not in rendered and "123.456.789-09" not in rendered
    assert "pessoa@empresa.com" not in rendered and "C:\\Users\\pessoa" not in rendered
    assert list(tmp_path.glob("*.tmp")) == []


def test_relatorio_recusa_catalogo_incompleto_e_extensao_incorreta(tmp_path):
    service = HelpCenterDiagnosticService(
        persistent_dirs=[tmp_path], database_probe=None, backup_probe=None,
        printer_probe=None, nabi_probe=None,
    )
    results = service.run()
    with pytest.raises(ValueError, match="resultado único"):
        service.report_bytes(results[:-1])
    with pytest.raises(ValueError, match="extensão"):
        service.save_report(tmp_path / "socorro.txt", results)


def test_falha_na_substituicao_remove_temporario_e_preserva_destino(tmp_path, monkeypatch):
    service = HelpCenterDiagnosticService(
        persistent_dirs=[tmp_path], database_probe=None, backup_probe=None,
        printer_probe=None, nabi_probe=None,
    )
    destination = tmp_path / "socorro.json"; destination.write_text("anterior", encoding="utf-8")
    monkeypatch.setattr("services.help_center_service.os.replace", lambda *_args: (_ for _ in ()).throw(OSError("bloqueado")))
    with pytest.raises(OSError): service.save_report(destination, service.run())
    assert destination.read_text(encoding="utf-8") == "anterior"
    assert not list(tmp_path.glob(".*.tmp"))
