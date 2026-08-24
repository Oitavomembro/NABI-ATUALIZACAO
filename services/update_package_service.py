from __future__ import annotations

import hmac
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from helpers.file_hashing import sha256_file
from core.runtime_profile import DatabaseUsageLock
from services.update_package_validation_service import UpdatePackageValidationService


class UpdatePackageService:
    """Validação, preparação, auditoria e recuperação de pacotes incrementais."""

    def __init__(
        self, *, app_dir: str | os.PathLike[str], install_dir: str | os.PathLike[str],
        current_version: str, trusted_public_keys: str | os.PathLike[str] | None = None,
    ) -> None:
        self.app_dir = Path(app_dir).expanduser().resolve()
        self.install_dir = Path(install_dir).expanduser().resolve()
        self.current_version = str(current_version).strip()
        self.update_dir = self.app_dir / "atualizacoes"
        self.state_file = self.app_dir / "estado_atualizacao.json"
        self.history_file = self.app_dir / "historico_atualizacoes.jsonl"
        self.current_revision = self._read_current_revision()
        catalog = Path(trusted_public_keys).resolve() if trusted_public_keys else self._catalog_path()
        self.validation_service = UpdatePackageValidationService(
            self.current_version, self.current_revision, trusted_public_keys=catalog,
        )

    def _catalog_path(self) -> Path:
        candidates = (
            self.install_dir / "licensing" / "trusted_public_keys.json",
            self.install_dir / "_internal" / "licensing" / "trusted_public_keys.json",
        )
        return next((path for path in candidates if path.is_file()), candidates[0])

    def _read_current_revision(self) -> int:
        for path in (self.install_dir / "REVISAO.txt", self.install_dir / "_internal" / "REVISAO.txt"):
            try:
                return max(0, int(path.read_text(encoding="utf-8-sig").strip()))
            except (OSError, UnicodeError, TypeError, ValueError):
                continue
        return 0

    version_tuple = staticmethod(UpdatePackageValidationService.version_tuple)
    sha256_bytes = staticmethod(UpdatePackageValidationService.sha256_bytes)

    sha256_file = staticmethod(sha256_file)

    @staticmethod
    def atomic_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def append_history(self, status: str, **details: Any) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        record = {"data": datetime.now().isoformat(timespec="seconds"), "status": status, **details}
        with self.history_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def validate(self, package_path: str | os.PathLike[str]) -> dict[str, Any]:
        return self.validation_service.validate(package_path)

    def prepare(self, package_path: str | os.PathLike[str], manifest: dict[str, Any], snapshot_id: str) -> dict[str, Any]:
        target_version = str(manifest["version"])
        target_revision = int(manifest.get("revision") or 0)
        tag = target_version.replace(".", "_") + f"_r{target_revision}"
        staging = self.update_dir / f"staging_{tag}"
        backup = self.update_dir / f"backup_arquivos_{tag}_{datetime.now():%Y%m%d_%H%M%S}"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        backup.mkdir(parents=True, exist_ok=False)

        with zipfile.ZipFile(package_path, "r") as archive:
            for item in manifest["files"]:
                relative = item["path"]
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(f"payload/{relative}") as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)

        backed_up: list[str] = []
        absent_before: list[str] = []
        affected = [item["path"] for item in manifest["files"]] + list(manifest.get("remove") or [])
        for relative in dict.fromkeys(affected):
            source = self.install_dir / relative
            if source.is_file():
                destination = backup / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                backed_up.append(relative)
            elif not source.exists():
                absent_before.append(relative)

        state = {
            "status": "PREPARADO",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_version": self.current_version,
            "target_version": target_version,
            "target_revision": target_revision,
            "manifest": manifest,
            "staging": str(staging),
            "file_backup": str(backup),
            "backed_up": backed_up,
            "absent_before": absent_before,
            "snapshot_id": snapshot_id,
            "install_dir": str(self.install_dir),
        }
        self.atomic_json(self.state_file, state)
        self.append_history("PREPARADO", origem=self.current_version, destino=target_version, snapshot=snapshot_id)
        return state

    def load_state(self) -> dict[str, Any] | None:
        if not self.state_file.is_file():
            return None
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def validate_installed_files(self, state: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for item in state.get("manifest", {}).get("files", []):
            path = self.install_dir / item["path"]
            if not path.is_file():
                errors.append(f"Ausente: {item['path']}")
            elif not hmac.compare_digest(self.sha256_file(path), str(item["sha256"]).lower()):
                errors.append(f"Hash divergente: {item['path']}")
        for relative in state.get("manifest", {}).get("remove", []):
            if (self.install_dir / relative).exists():
                errors.append(f"Arquivo obsoleto não removido: {relative}")
        return errors

    def mark_success(self, state: dict[str, Any], report: dict[str, Any]) -> None:
        state = dict(state)
        state.update(status="CONCLUIDO", completed_at=datetime.now().isoformat(timespec="seconds"), report=report)
        self.atomic_json(self.state_file, state)
        self.append_history("CONCLUIDO", origem=state.get("source_version"), destino=state.get("target_version"), report=report)

    def restore_files(self, state: dict[str, Any]) -> None:
        backup = Path(state["file_backup"])
        for relative in state.get("backed_up", []):
            source = backup / relative
            destination = self.install_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for relative in state.get("absent_before", []):
            destination = self.install_dir / relative
            if destination.is_file() or destination.is_symlink():
                destination.unlink()
            elif destination.is_dir():
                shutil.rmtree(destination)

    def mark_failure(self, state: dict[str, Any], error: str, *, rolled_back: bool) -> None:
        state = dict(state)
        state.update(
            status="ROLLBACK_CONCLUIDO" if rolled_back else "FALHA",
            failed_at=datetime.now().isoformat(timespec="seconds"),
            error=str(error),
        )
        self.atomic_json(self.state_file, state)
        self.append_history(state["status"], origem=state.get("source_version"), destino=state.get("target_version"), erro=str(error))


def _original_process_alive(pid: int, expected_started_at: float | None) -> bool:
    if not DatabaseUsageLock._pid_alive(int(pid)):
        return False
    if expected_started_at is None:
        return True
    actual_started_at = DatabaseUsageLock._process_started_at(int(pid))
    if actual_started_at is None:
        return True
    return abs(actual_started_at - float(expected_started_at)) <= 2.0


def apply_prepared_update(
    state_file: str,
    *,
    pid: int,
    launcher: str,
    source_main: str | None = None,
    process_started_at: float | None = None,
) -> int:
    """Executado em processo separado: espera o app fechar, aplica e reabre."""
    import subprocess
    import time

    state_path = Path(state_file).expanduser().resolve()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    install_dir = Path(state["install_dir"])
    staging = Path(state["staging"])
    backup = Path(state["file_backup"])

    def write_status(status: str, **extra: Any) -> None:
        state.update(status=status, **extra)
        UpdatePackageService.atomic_json(state_path, state)

    deadline = time.time() + 120
    while time.time() < deadline:
        if not _original_process_alive(pid, process_started_at):
            break
        time.sleep(0.5)
    else:
        write_status("FALHA", error="O processo anterior não encerrou no prazo.")
        return 2

    try:
        write_status("APLICANDO", apply_started_at=datetime.now().isoformat(timespec="seconds"))
        for item in state.get("manifest", {}).get("files", []):
            relative = item["path"]
            source = staging / relative
            destination = install_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".update.tmp")
            shutil.copy2(source, temporary)
            os.replace(temporary, destination)
        for relative in state.get("manifest", {}).get("remove", []):
            destination = install_dir / relative
            if destination.is_file() or destination.is_symlink():
                destination.unlink()
            elif destination.is_dir():
                shutil.rmtree(destination)
        write_status("ARQUIVOS_APLICADOS", applied_at=datetime.now().isoformat(timespec="seconds"))
    except Exception as exc:
        try:
            for relative in state.get("backed_up", []):
                source = backup / relative
                destination = install_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            for relative in state.get("absent_before", []):
                destination = install_dir / relative
                if destination.is_file() or destination.is_symlink():
                    destination.unlink()
                elif destination.is_dir():
                    shutil.rmtree(destination)
            write_status("ROLLBACK_ARQUIVOS", error=str(exc), rolled_back_at=datetime.now().isoformat(timespec="seconds"))
        except Exception as rollback_exc:
            write_status("FALHA_CRITICA", error=str(exc), rollback_error=str(rollback_exc))
        return 3

    command = [launcher]
    if source_main:
        command.append(source_main)
    subprocess.Popen(command, cwd=str(install_dir))
    return 0


def rollback_prepared_update(
    state_file: str, *, pid: int, launcher: str, source_main: str | None = None,
    process_started_at: float | None = None,
) -> int:
    """Restaura arquivos pelo helper externo depois que o app atualizado fecha."""
    import subprocess
    import time

    state_path = Path(state_file).expanduser().resolve()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    deadline = time.time() + 120
    while time.time() < deadline:
        if not _original_process_alive(pid, process_started_at): break
        time.sleep(0.5)
    else:
        state.update(status="FALHA", error="O processo atualizado não encerrou no prazo.")
        UpdatePackageService.atomic_json(state_path, state)
        return 2
    try:
        service = object.__new__(UpdatePackageService)
        service.install_dir = Path(state["install_dir"])
        UpdatePackageService.restore_files(service, state)
        state.update(status="ROLLBACK_CONCLUIDO", rolled_back_at=datetime.now().isoformat(timespec="seconds"))
        UpdatePackageService.atomic_json(state_path, state)
    except Exception as error:
        state.update(status="FALHA_CRITICA", rollback_error=str(error))
        UpdatePackageService.atomic_json(state_path, state)
        return 3
    command = [launcher]
    if source_main: command.append(source_main)
    subprocess.Popen(command, cwd=str(Path(state["install_dir"])))
    return 0
