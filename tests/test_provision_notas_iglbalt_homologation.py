from __future__ import annotations

import base64
from pathlib import Path

from build_tools import provision_notas_iglbalt_homologation as ceremony


class Protector:
    def __init__(self, **_kwargs): pass
    def protect(self, value): return b"TEST-DPAPI:" + value


def test_cerimonia_cria_material_publico_e_segredo_separados(tmp_path, monkeypatch):
    monkeypatch.setattr(ceremony, "WindowsDataProtector", Protector)
    secret_dir = tmp_path / "segredos"
    license_dir = tmp_path / "licencas"
    result = ceremony.provision(secret_dir, license_dir)
    assert result["key_id"] == "notas-iglbalt-prod-2026-01"
    assert len(base64.b64decode(result["public_key_base64"], validate=True)) == 32
    assert Path(result["license_path"]).is_file()
    assert Path(result["private_key_path"]).parent == secret_dir
    assert b"PRIVATE KEY" not in Path(result["license_path"]).read_bytes()


def test_cerimonia_nunca_sobrescreve_material_existente(tmp_path, monkeypatch):
    monkeypatch.setattr(ceremony, "WindowsDataProtector", Protector)
    secret_dir = tmp_path / "segredos"
    license_dir = tmp_path / "licencas"
    ceremony.provision(secret_dir, license_dir)
    try:
        ceremony.provision(secret_dir, license_dir)
    except FileExistsError:
        pass
    else:
        raise AssertionError("cerimônia sobrescreveu material permanente")
