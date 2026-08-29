from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path

import pytest

from services.fiscal_regulatory_catalog_service import (
    FiscalRegulatoryCatalogService,
)


ROOT = Path(__file__).resolve().parents[1]


def test_catalogo_oficial_instalado_e_atual_para_homologacao():
    report = FiscalRegulatoryCatalogService(
        runtime_root=ROOT, today_provider=lambda: date(2026, 8, 29)
    ).audit(environment="HOMOLOGACAO")

    assert report.ready
    assert report.jurisdiction == "BR-BA"
    assert ("nfe-schemas-010e-v1.02", "010e v1.02") in report.artifact_versions
    assert "sale" in report.supported_operations
    assert "general_tax_matrix" in report.unsupported_operations


def test_catalogo_vencido_bloqueia_sem_consultar_rede():
    report = FiscalRegulatoryCatalogService(
        runtime_root=ROOT, today_provider=lambda: date(2026, 10, 1)
    ).audit(environment="HOMOLOGACAO")

    assert not report.ready
    assert any("Revisão regulatória vencida" in problem for problem in report.problems)


def test_catalogo_nao_autoriza_producao():
    report = FiscalRegulatoryCatalogService(
        runtime_root=ROOT, today_provider=lambda: date(2026, 8, 29)
    ).audit(environment="PRODUCAO")

    assert not report.ready
    assert any("não autoriza operação em produção" in problem for problem in report.problems)


def test_adulteracao_do_catalogo_falha_fechada(tmp_path):
    source = ROOT / "resources" / "fiscal" / "regulatory_catalog.json"
    target = tmp_path / "catalog.json"
    target.write_bytes(source.read_bytes() + b"\n")

    report = FiscalRegulatoryCatalogService(
        runtime_root=ROOT, catalog_path=target,
        today_provider=lambda: date(2026, 8, 29),
    ).audit()

    assert not report.ready
    assert any("alterado" in problem for problem in report.problems)


def test_fonte_nao_oficial_e_artefato_ausente_sao_bloqueados(tmp_path):
    payload = json.loads(
        (ROOT / "resources" / "fiscal" / "regulatory_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    payload["artifacts"][0]["source_url"] = "https://example.invalid/schema.zip"
    payload["artifacts"][0]["installed_path"] = "resources/fiscal/schemas/ausente.xsd"
    target = tmp_path / "catalog.json"
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(target.read_bytes()).hexdigest().upper()

    report = FiscalRegulatoryCatalogService(
        runtime_root=ROOT, catalog_path=target, expected_sha256=digest,
        today_provider=lambda: date(2026, 8, 29),
    ).audit()

    assert not report.ready
    assert any("fonte oficial" in problem for problem in report.problems)
    assert any("instalado ausente" in problem for problem in report.problems)


def test_require_current_propaga_todos_os_bloqueios():
    service = FiscalRegulatoryCatalogService(
        runtime_root=ROOT, today_provider=lambda: date(2026, 8, 29)
    )
    with pytest.raises(ValueError, match="não autoriza operação em produção"):
        service.require_current(environment="PRODUCAO")
