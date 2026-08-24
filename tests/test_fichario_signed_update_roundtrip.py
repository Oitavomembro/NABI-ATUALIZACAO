from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from database.maintenance import DatabaseMaintenanceService
from services.update_package_service import UpdatePackageService, apply_prepared_update
from services.update_signature import sign_update_manifest


def _database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
        INSERT INTO configuracoes VALUES('db_schema_version','20');
        CREATE TABLE clientes(id INTEGER PRIMARY KEY, nome TEXT);
        INSERT INTO clientes VALUES(7,'CLIENTE PRESERVADO');
        CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY);
        CREATE TABLE parcelas(id INTEGER PRIMARY KEY);
        CREATE TABLE historico_clientes(id INTEGER PRIMARY KEY);
    """)
    connection.commit(); connection.close()


def _customer_names(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try: return [str(row[0]) for row in connection.execute("SELECT nome FROM clientes")]
    finally: connection.close()


def test_signed_clock_update_preserves_database_and_can_rollback(tmp_path):
    install = tmp_path / "install"; appdata = tmp_path / "appdata"
    install.mkdir(); (install / "licensing").mkdir()
    (install / "VERSAO.txt").write_text("2.5.1\n", encoding="utf-8")
    (install / "REVISAO.txt").write_text("19\n", encoding="utf-8")
    signer = Ed25519PrivateKey.generate()
    public = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    (install / "licensing" / "trusted_public_keys.json").write_text(json.dumps({
        "schema": 1,
        "keys": {"homolog-update": base64.b64encode(public).decode("ascii")},
    }), encoding="utf-8")

    marker = "23/08/2026 18:45:37\n".encode()
    files = {"REVISAO.txt": b"20\n", "ATUALIZADO_EM.txt": marker}
    manifest = sign_update_manifest({
        "product": "NabiCode", "version": "2.5.1", "revision": 20,
        "minimum_source_version": "2.5.1", "accepted_source_versions": ["2.5.1"],
        "files": [
            {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in files.items()
        ],
        "remove": [], "created_at": "2026-08-23T18:45:37",
    }, key_id="homolog-update", signer=signer)
    package = tmp_path / "atualizacao_relogio_assinada.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, data in files.items(): archive.writestr(f"payload/{name}", data)

    database = appdata / "fichario.db"; appdata.mkdir(); _database(database)
    maintenance = DatabaseMaintenanceService(
        database, appdata / "backups", expected_schema_version=20,
        required_tables=("clientes", "movimentacoes", "parcelas", "historico_clientes"),
    )
    backup, report = maintenance.create_backup(prefix="antes_atualizacao")
    assert report.valid
    service = UpdatePackageService(
        app_dir=appdata, install_dir=install, current_version="2.5.1",
    )
    validated = service.validate(package)
    state = service.prepare(package, validated, str(backup))
    noop = tmp_path / "reopen_noop.py"; noop.write_text("pass\n", encoding="utf-8")
    assert apply_prepared_update(
        str(service.state_file), pid=999_999_999, launcher=sys.executable,
        source_main=str(noop),
    ) == 0
    assert (install / "ATUALIZADO_EM.txt").read_text() == "23/08/2026 18:45:37\n"
    assert (install / "REVISAO.txt").read_text() == "20\n"
    assert _customer_names(database) == ["CLIENTE PRESERVADO"]
    assert service.validate_installed_files(state) == []
    persisted = json.loads(service.state_file.read_text(encoding="utf-8"))
    protected = Path(persisted["file_backup"])
    assert protected.parent == install / ".nabicode_rollback"
    assert (protected / "REVISAO.txt").read_text(encoding="utf-8") == "19\n"

    (install / "ATUALIZADO_EM.txt").write_text("CORROMPIDO", encoding="utf-8")
    assert service.validate_installed_files(state)
    service.restore_files(state)
    maintenance.restore(backup)
    assert not (install / "ATUALIZADO_EM.txt").exists()
    assert (install / "REVISAO.txt").read_text() == "19\n"
    assert _customer_names(database) == ["CLIENTE PRESERVADO"]
