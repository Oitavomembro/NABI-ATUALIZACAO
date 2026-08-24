from __future__ import annotations

import hmac
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from helpers.file_hashing import sha256_file
from core.runtime_profile import DatabaseUsageLock
from services.update_package_validation_service import UpdatePackageValidationService
from services.update_signature import load_public_catalog, verify_update_manifest
from licensing.license_format import canonical_json


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
        # Reabre e revalida o pacote imediatamente antes de extrair. A seleção
        # feita pela interface pode ter sido trocada entre a prévia e esta etapa.
        revalidated = self.validate(package_path)
        if revalidated != manifest:
            raise ValueError("O pacote mudou depois da validação inicial.")
        manifest = revalidated
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

        for item in manifest["files"]:
            staged = staging / item["path"]
            if not staged.is_file() or not hmac.compare_digest(
                self.sha256_file(staged), str(item["sha256"]).lower(),
            ):
                shutil.rmtree(staging, ignore_errors=True)
                shutil.rmtree(backup, ignore_errors=True)
                raise ValueError(f"Arquivo preparado diverge do pacote: {item['path']}.")

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


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _safe_update_relative(value: object) -> str:
    raw = str(value or "").replace("\\", "/")
    if raw.startswith("/"):
        raise ValueError(f"Caminho inseguro no estado da atualização: {value!r}.")
    text = raw
    candidate = Path(text)
    if (
        not text or candidate.is_absolute() or candidate.drive
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise ValueError(f"Caminho inseguro no estado da atualização: {value!r}.")
    return text


def validate_prepared_state(state_path: Path, state: dict[str, Any], install_dir: Path) -> dict[str, Any]:
    """Revalida o estado editável antes de qualquer escrita pelo helper."""

    install_dir = install_dir.resolve()
    recorded_install = Path(str(state.get("install_dir") or "")).resolve()
    if recorded_install != install_dir:
        raise ValueError("O diretório de instalação do estado não corresponde ao atualizador.")
    status = state.get("status")
    if status not in {"PREPARADO", "ROLLBACK_PENDENTE"}:
        raise ValueError("Estado da atualização não está apto para aplicação ou rollback.")

    manifest = state.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError("Manifesto ausente no estado da atualização.")
    catalog_candidates = (
        install_dir / "licensing" / "trusted_public_keys.json",
        install_dir / "_internal" / "licensing" / "trusted_public_keys.json",
    )
    catalog = next((path for path in catalog_candidates if path.is_file()), catalog_candidates[0])
    verify_update_manifest(manifest, load_public_catalog(catalog))

    update_root = (state_path.resolve().parent / "atualizacoes").resolve()
    staging = Path(str(state.get("staging") or "")).resolve()
    backup = Path(str(state.get("file_backup") or "")).resolve()
    if not _is_within(staging, update_root):
        raise ValueError("Staging está fora da área de atualização.")
    if status == "PREPARADO":
        if not _is_within(backup, update_root):
            raise ValueError("Backup preparatório está fora da área de atualização.")
    else:
        expected_backup = protected_backup_directory(install_dir, manifest)
        if backup != expected_backup or not _is_within(backup, install_dir / ".nabicode_rollback"):
            raise ValueError("Rollback não aponta para o backup protegido desta atualização.")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Manifesto não contém arquivos aplicáveis.")
    normalized_files: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Entrada de arquivo inválida no manifesto.")
        relative = _safe_update_relative(item.get("path"))
        expected = str(item.get("sha256") or "").lower()
        source = (staging / relative).resolve()
        destination = (install_dir / relative).resolve()
        if not _is_within(source, staging) or not _is_within(destination, install_dir):
            raise ValueError(f"Arquivo escaparia da área permitida: {relative}.")
        if not source.is_file() or not hmac.compare_digest(sha256_file(source), expected):
            raise ValueError(f"Arquivo preparado inválido: {relative}.")
        normalized_files.append({**item, "path": relative, "sha256": expected})

    normalized_remove = [_safe_update_relative(value) for value in manifest.get("remove") or []]
    normalized_backed_up = [_safe_update_relative(value) for value in state.get("backed_up") or []]
    normalized_absent = [_safe_update_relative(value) for value in state.get("absent_before") or []]
    signed_paths = {item["path"] for item in normalized_files} | set(normalized_remove)
    if not set(normalized_backed_up).issubset(signed_paths) or not set(normalized_absent).issubset(signed_paths):
        raise ValueError("Estado de rollback contém caminho não assinado.")

    validated = dict(state)
    validated["manifest"] = {**manifest, "files": normalized_files, "remove": normalized_remove}
    validated["backed_up"] = normalized_backed_up
    validated["absent_before"] = normalized_absent
    validated["install_dir"] = str(install_dir)
    validated["staging"] = str(staging)
    validated["file_backup"] = str(backup)
    return validated


def protected_backup_directory(install_dir: Path, manifest: dict[str, Any]) -> Path:
    identity = hashlib.sha256(canonical_json(manifest)).hexdigest()[:24]
    return (install_dir.resolve() / ".nabicode_rollback" / identity).resolve()


def create_protected_file_backup(
    state_path: Path, state: dict[str, Any], install_dir: Path,
) -> dict[str, Any]:
    """Cria o rollback com ACL herdada da instalação, fora do AppData editável."""

    backup = protected_backup_directory(install_dir, state["manifest"])
    rollback_root = (install_dir.resolve() / ".nabicode_rollback").resolve()
    if not _is_within(backup, rollback_root):
        raise ValueError("Diretório de rollback protegido inválido.")
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True, exist_ok=False)

    backed_up: list[str] = []
    absent_before: list[str] = []
    affected = [
        item["path"] for item in state["manifest"]["files"]
    ] + list(state["manifest"].get("remove") or [])
    for relative in dict.fromkeys(affected):
        relative = _safe_update_relative(relative)
        source = (install_dir / relative).resolve()
        if not _is_within(source, install_dir):
            raise ValueError(f"Origem de backup fora da instalação: {relative}.")
        if source.is_file():
            destination = (backup / relative).resolve()
            if not _is_within(destination, backup):
                raise ValueError(f"Destino de backup inseguro: {relative}.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            backed_up.append(relative)
        elif not source.exists():
            absent_before.append(relative)

    protected = dict(state)
    protected.update(
        status="BACKUP_PROTEGIDO", file_backup=str(backup),
        backed_up=backed_up, absent_before=absent_before,
        protected_at=datetime.now().isoformat(timespec="seconds"),
    )
    UpdatePackageService.atomic_json(state_path, protected)
    return protected


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
    use_shell_broker: bool = False,
) -> int:
    """Executado em processo separado: espera o app fechar, aplica e reabre."""
    import subprocess
    import time

    state_path = Path(state_file).expanduser().resolve()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    pinned_install = Path(getattr(sys, "executable", "")).resolve().parent if getattr(sys, "frozen", False) else Path(state["install_dir"]).resolve()
    state = validate_prepared_state(state_path, state, pinned_install)
    install_dir = pinned_install
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
        state = create_protected_file_backup(state_path, state, install_dir)
        backup = Path(state["file_backup"])
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
    if use_shell_broker and os.name == "nt":
        subprocess.Popen(["explorer.exe", *command], cwd=str(install_dir))
    else:
        subprocess.Popen(command, cwd=str(install_dir))
    return 0


def rollback_prepared_update(
    state_file: str, *, pid: int, launcher: str, source_main: str | None = None,
    process_started_at: float | None = None,
    use_shell_broker: bool = False,
) -> int:
    """Restaura arquivos pelo helper externo depois que o app atualizado fecha."""
    import subprocess
    import time

    state_path = Path(state_file).expanduser().resolve()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    pinned_install = Path(getattr(sys, "executable", "")).resolve().parent if getattr(sys, "frozen", False) else Path(state["install_dir"]).resolve()
    state = validate_prepared_state(state_path, state, pinned_install)
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
        service.install_dir = pinned_install
        UpdatePackageService.restore_files(service, state)
        state.update(status="ROLLBACK_CONCLUIDO", rolled_back_at=datetime.now().isoformat(timespec="seconds"))
        UpdatePackageService.atomic_json(state_path, state)
    except Exception as error:
        state.update(status="FALHA_CRITICA", rollback_error=str(error))
        UpdatePackageService.atomic_json(state_path, state)
        return 3
    command = [launcher]
    if source_main: command.append(source_main)
    if use_shell_broker and os.name == "nt":
        subprocess.Popen(["explorer.exe", *command], cwd=str(pinned_install))
    else:
        subprocess.Popen(command, cwd=str(pinned_install))
    return 0
