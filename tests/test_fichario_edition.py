from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fichario.license_policy import FicharioLicensePolicy
from licensing.models import LicenseDecision, LicenseEdition, LicensePayload, LicenseState


def decision(edition=LicenseEdition.FICHARIO, features=("fichario", "qt", "commercial", "financial")):
    payload = LicensePayload(
        schema=2, license_id=str(uuid4()), edition=edition, customer_name="LOJA TESTE",
        machine_fingerprint="a" * 64, issued_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        valid_until=date(2026, 9, 1), grace_days=10, features=features,
    )
    return LicenseDecision(LicenseState.ACTIVE, "VALID", "NABI2-TESTE", payload)


def test_edicao_exige_declaracao_fichario_assinada_e_recursos_completos():
    assert FicharioLicensePolicy(decision()).operational
    assert not FicharioLicensePolicy(decision(LicenseEdition.COMMERCIAL)).operational
    assert not FicharioLicensePolicy(decision(features=("fichario", "qt"))).operational
    assert not FicharioLicensePolicy(decision(features=(
        "fichario", "qt", "commercial", "financial", "fiscal"
    ))).operational


def test_estado_nao_operacional_falha_fechado():
    blocked = LicenseDecision(LicenseState.BLOCKED, "EXPIRED", "NABI2-TESTE")
    policy = FicharioLicensePolicy(blocked)
    assert not policy.operational
    with pytest.raises(PermissionError): policy.require()


def test_perfil_fichario_isola_dados_fora_do_programa(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("NABICODE_PROFILE", "TESTE")
    from fichario.profile import configure_fichario_profile
    profile = configure_fichario_profile()
    assert profile.app_dir == (tmp_path / "NabiCode" / "Fichario" / "Teste").resolve()
    assert profile.paths.database.parent == profile.app_dir
    assert "Program Files" not in str(profile.app_dir)


def test_composicao_e_pacote_nao_iniciam_componentes_proibidos():
    root = Path(__file__).parents[1]
    own = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in [root / "main_fichario_qt.py", *sorted((root / "fichario").glob("*.py"))]
    )
    for forbidden in (
        "assistant_nabi", "fiscalworker", "fiscal_outbox", "sefaz", "certificado", "nfeimport",
    ):
        assert forbidden not in own
    spec = (root / "build_tools/pyinstaller/nabicode_fichario.spec").read_text(
        encoding="utf-8"
    ).casefold()
    assert "resources/fiscal" not in spec
    assert "main_fichario_qt.py" in spec
    assert "assistant_nabi" in spec  # exclusao explicita do pacote


def test_instalador_preserva_dados_em_appdata():
    source = (Path(__file__).parents[1] / "build_tools/inno/NabiCode_Fichario_Offline.iss").read_text(
        encoding="utf-8"
    ).casefold()
    assert "nabicode fichario" in source
    assert "deltree" not in source
    assert "{userappdata}" not in source
