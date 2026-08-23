from __future__ import annotations

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from license_issuer.emitter import generate_key_pair, issue_license, load_private_key
from licensing.models import LicenseEdition
from licensing.runtime import load_trusted_public_keys


ROOT = Path(__file__).resolve().parents[1]


def test_catalogo_publico_estrito_e_catalogo_vazio_falha_fechado(tmp_path):
    catalog = tmp_path / "keys.json"
    catalog.write_text('{"schema":1,"keys":{}}', encoding="utf-8")
    assert load_trusted_public_keys(catalog) == {}
    catalog.write_text('{"schema":1,"keys":{"owner":"invalida"}}', encoding="utf-8")
    assert load_trusted_public_keys(catalog) == {}


def test_emissor_grava_chave_privada_somente_fora_do_repositorio(tmp_path):
    private_path = tmp_path / "secrets" / "owner.pem"
    public_path = tmp_path / "trusted.json"
    generate_key_pair(
        private_path, public_path, key_id="owner-2026",
        password=b"senha-forte-teste",
    )
    assert private_path.is_file()
    catalog = load_trusted_public_keys(public_path)
    assert len(catalog["owner-2026"]) == 32
    key = load_private_key(private_path, password=b"senha-forte-teste")
    assert key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw) == catalog["owner-2026"]


def test_emissor_recusa_destino_privado_dentro_do_repositorio(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="fora do repositório"):
        generate_key_pair(
            ROOT / "private-never.pem", tmp_path / "public.json",
            key_id="owner", password=b"senha-forte-teste",
        )
    assert not (ROOT / "private-never.pem").exists()


def test_runtime_nao_importa_emissor_e_repositorio_nao_contem_pem_privado():
    runtime_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "licensing").glob("*.py")
    )
    assert "license_issuer" not in runtime_sources
    private_markers = []
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".pem", ".key"}:
            if "PRIVATE KEY" in path.read_text(encoding="utf-8", errors="ignore"):
                private_markers.append(path)
    assert private_markers == []


def test_entrypoints_bloqueiam_antes_de_banco_worker_e_import_legacy():
    legacy = (ROOT / "main.py").read_text(encoding="utf-8")
    qt = (ROOT / "main_qt.py").read_text(encoding="utf-8")
    legacy_main = legacy.index("def main()")
    legacy_gate = legacy.index("evaluate_runtime_gate(runtime_profile.app_dir)")
    assert legacy_gate < legacy.index("_run_update_helper()", legacy_main)
    assert legacy_gate < legacy.index("import nabicode_legacy as legacy")
    qt_gate = qt.index("evaluate_runtime_gate(profile.app_dir)")
    assert qt_gate < qt.index("_network_configuration(profile)", qt.index("def main"))
    assert qt_gate < qt.index("DatabaseManager(database_path", qt.index("def main"))


def test_licenciamento_nao_importa_modulos_fiscais_ia_ou_banco():
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "licensing").glob("*.py")
    )
    for forbidden in (
        "assistant_nabi", "fiscal_service", "fiscal_outbox", "database import", "sqlite3",
    ):
        assert forbidden not in sources
