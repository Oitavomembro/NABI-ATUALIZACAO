from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path

from helpers.file_hashing import sha256_file
from services.admin_audit_service import AdminAuditService


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _wait_for_parent(parent_pid: int, timeout: float = 120.0) -> None:
    if parent_pid <= 0:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(parent_pid, 0)
        except OSError:
            return
        time.sleep(0.2)
    raise TimeoutError("O NabiCode não encerrou a tempo; restauração não aplicada.")


def _validate_database(path: Path) -> None:
    connection = sqlite3.connect(str(path))
    try:
        integrity = tuple(row[0] for row in connection.execute("PRAGMA integrity_check"))
        foreign_keys = tuple(connection.execute("PRAGMA foreign_key_check"))
    finally:
        connection.close()
    if integrity != ("ok",) or foreign_keys:
        raise RuntimeError("Banco restaurado reprovado na validação final.")


def apply_prepared_restore(request_file, database_path, staging_root, *, parent_pid=0) -> None:
    request = Path(request_file).resolve()
    database = Path(database_path).resolve()
    root = Path(staging_root).resolve()
    if request.name != "restore-request.json" or not _inside(request, root):
        raise ValueError("Solicitação fora da área de restauração autorizada.")
    payload = json.loads(request.read_text(encoding="utf-8"))
    required = {
        "schema", "request_id", "actor", "profile_database_name",
        "active_database_sha256", "staged_file", "staged_sha256",
        "source_sha256", "safety_backup", "safety_backup_sha256", "status",
    }
    if set(payload) != required or payload["schema"] != "nabicode.restore-request.v1":
        raise ValueError("Contrato da solicitação de restauração inválido.")
    operation = request.parent.resolve()
    if operation.parent != root or operation.name != payload["request_id"]:
        raise ValueError("Identidade da operação de restauração inválida.")
    staged = (operation / str(payload["staged_file"])).resolve()
    safety = Path(str(payload["safety_backup"])).resolve()
    if staged.parent != operation or staged.name != "database.staged.db":
        raise ValueError("Banco preparado fora da operação autorizada.")
    if database.name != payload["profile_database_name"]:
        raise ValueError("Perfil de banco divergente da solicitação.")
    if payload["status"] != "AGUARDANDO_HELPER_OFICIAL":
        raise ValueError("Solicitação já consumida ou em estado inválido.")
    for path, expected in (
        (database, payload["active_database_sha256"]),
        (staged, payload["staged_sha256"]),
        (safety, payload["safety_backup_sha256"]),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError("Arquivo da restauração ausente ou alterado.")
    _validate_database(staged)
    _wait_for_parent(int(parent_pid))
    if sha256_file(database) != payload["active_database_sha256"]:
        raise RuntimeError("O banco ativo mudou após a preparação; restauração cancelada.")

    incoming = database.with_name(f".{database.name}.{operation.name}.incoming")
    displaced = database.with_name(f".{database.name}.{operation.name}.previous")
    active_sidecars = tuple(Path(f"{database}{suffix}") for suffix in ("-wal", "-shm"))
    displaced_sidecars = tuple(Path(f"{displaced}{suffix}") for suffix in ("-wal", "-shm"))
    try:
        shutil.copy2(staged, incoming)
        if sha256_file(incoming) != payload["staged_sha256"]:
            raise RuntimeError("Cópia preparada divergiu antes da substituição.")
        os.replace(database, displaced)
        for active_sidecar, displaced_sidecar in zip(active_sidecars, displaced_sidecars):
            if active_sidecar.exists():
                os.replace(active_sidecar, displaced_sidecar)
        os.replace(incoming, database)
        _validate_database(database)
        audit = AdminAuditService(lambda: sqlite3.connect(str(database)))
        audit.record_event_strict(
            "technical", "RESTAURACAO_APLICADA", object_id=operation.name,
            details=f"origem={str(payload['source_sha256'])[:16]};prebackup={safety.name}",
            user=str(payload["actor"]),
        )
    except Exception:
        incoming.unlink(missing_ok=True)
        if displaced.is_file():
            database.unlink(missing_ok=True)
            os.replace(displaced, database)
            for active_sidecar, displaced_sidecar in zip(active_sidecars, displaced_sidecars):
                active_sidecar.unlink(missing_ok=True)
                if displaced_sidecar.exists():
                    os.replace(displaced_sidecar, active_sidecar)
            _validate_database(database)
        raise
    displaced.unlink(missing_ok=True)
    for displaced_sidecar in displaced_sidecars:
        displaced_sidecar.unlink(missing_ok=True)
    payload["status"] = "APLICADA"
    payload["applied_database_sha256"] = sha256_file(database)
    temporary = request.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(temporary, request)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--request", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--staging-root", required=True)
    parser.add_argument("--parent-pid", type=int, default=0)
    args = parser.parse_args(argv)
    apply_prepared_restore(
        args.request, args.database, args.staging_root, parent_pid=args.parent_pid,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
