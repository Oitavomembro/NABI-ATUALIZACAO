from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from helpers.file_hashing import sha256_file
from services.database_restore_helper import apply_prepared_restore


def _database(path: Path, marker: str, *, audit=True) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE dados(valor TEXT)")
    connection.execute("INSERT INTO dados VALUES (?)", (marker,))
    if audit:
        connection.execute(
            "CREATE TABLE auditoria(id INTEGER PRIMARY KEY, data TEXT, usuario TEXT, "
            "modulo TEXT, acao TEXT, objeto TEXT, detalhes TEXT, resultado TEXT)"
        )
    connection.commit(); connection.close()


def _request(tmp_path, *, staged_audit=True):
    active = tmp_path / "active.db"; _database(active, "anterior")
    safety = tmp_path / "safety.db"; safety.write_bytes(active.read_bytes())
    root = tmp_path / "staging"; operation = root / "restore_abc"; operation.mkdir(parents=True)
    staged = operation / "database.staged.db"; _database(staged, "restaurado", audit=staged_audit)
    request = operation / "restore-request.json"
    payload = {
        "schema": "nabicode.restore-request.v1", "request_id": operation.name,
        "actor": "admin", "profile_database_name": active.name,
        "active_database_sha256": sha256_file(active), "staged_file": staged.name,
        "staged_sha256": sha256_file(staged), "source_sha256": "f" * 64,
        "safety_backup": str(safety), "safety_backup_sha256": sha256_file(safety),
        "status": "AGUARDANDO_HELPER_OFICIAL",
    }
    request.write_text(json.dumps(payload), encoding="utf-8")
    return request, active, root


def test_helper_aplica_fora_do_processo_e_registra_auditoria(tmp_path):
    request, active, root = _request(tmp_path)
    Path(f"{active}-wal").write_bytes(b"wal-anterior")
    Path(f"{active}-shm").write_bytes(b"shm-anterior")
    apply_prepared_restore(request, active, root)
    connection = sqlite3.connect(active)
    try:
        assert connection.execute("SELECT valor FROM dados").fetchone()[0] == "restaurado"
        assert connection.execute("SELECT acao FROM auditoria").fetchone()[0] == "RESTAURACAO_APLICADA"
    finally:
        connection.close()
    assert json.loads(request.read_text(encoding="utf-8"))["status"] == "APLICADA"
    assert not Path(f"{active}-wal").exists()
    assert not Path(f"{active}-shm").exists()


def test_falha_da_auditoria_restaura_exatamente_o_banco_anterior(tmp_path):
    request, active, root = _request(tmp_path, staged_audit=False)
    before = active.read_bytes()
    Path(f"{active}-wal").write_bytes(b"wal-anterior")
    Path(f"{active}-shm").write_bytes(b"shm-anterior")
    with pytest.raises(RuntimeError, match="Auditoria crítica"):
        apply_prepared_restore(request, active, root)
    assert active.read_bytes() == before
    assert not tuple(tmp_path.glob("*.previous*"))


def test_hash_alterado_bloqueia_antes_de_substituir(tmp_path):
    request, active, root = _request(tmp_path)
    before = active.read_bytes()
    staged = request.parent / "database.staged.db"
    staged.write_bytes(staged.read_bytes() + b"alterado")
    with pytest.raises(RuntimeError, match="ausente ou alterado"):
        apply_prepared_restore(request, active, root)
    assert active.read_bytes() == before
