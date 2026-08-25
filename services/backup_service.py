from __future__ import annotations

import os
import hashlib
import json
import threading
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from database.sqlite_connection import backup_database, open_connection
from services.backup_envelope import (
    BackupEnvelopeInfo,
    decrypt_database,
    encrypt_database,
    file_sha256,
    inspect_envelope,
)


@dataclass(frozen=True)
class BackupResult:
    created: tuple[str, ...]
    errors: tuple[str, ...]
    skipped: bool = False
    fiscal_archives: tuple[str, ...] = ()
    destinations: tuple["BackupDestinationResult", ...] = ()

    @property
    def status(self) -> str:
        if self.skipped:
            return "DESATIVADO" if not self.destinations else "JA_CONCLUIDO"
        succeeded = sum(item.succeeded for item in self.destinations)
        failed = sum(not item.succeeded for item in self.destinations)
        if succeeded and failed:
            return "PARCIAL"
        return "SUCESSO" if succeeded else "FALHA"


@dataclass(frozen=True)
class BackupDestinationResult:
    directory: str
    succeeded: bool
    skipped: bool = False
    database_backup: str = ""
    fiscal_archive: str = ""
    error: str = ""


@dataclass(frozen=True)
class RestoreVerificationResult:
    source: str
    sha256: str
    integrity: str
    foreign_key_errors: tuple[tuple, ...]
    schema_version: int
    backup_format: str = "SQLITE_LEGACY_UNENCRYPTED"
    encrypted: bool = False


class BackupService:
    """Centraliza backups manuais e diários com validação SQLite obrigatória."""

    _daily_lock = threading.Lock()

    def __init__(
        self,
        *,
        database_path: str | os.PathLike[str],
        default_directory: str | os.PathLike[str],
        get_config: Callable[[str], str | None],
        set_config: Callable[[str, str], None],
        fiscal_directory: str | os.PathLike[str] | None = None,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.database_path = Path(database_path)
        self.default_directory = Path(default_directory)
        self.get_config = get_config
        self.set_config = set_config
        self.fiscal_directory = Path(fiscal_directory).resolve() if fiscal_directory else None
        self.now = now

    def configured_directories(self) -> list[str]:
        local = (self.get_config("pasta_backup_local") or str(self.default_directory)).strip()
        cloud = (self.get_config("pasta_backup_nuvem") or "").strip()
        unique: list[str] = []
        seen: set[str] = set()
        for raw in (local, cloud):
            if not raw:
                continue
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = self.default_directory.parent / candidate
            normalized = str(candidate.resolve())
            key = os.path.normcase(normalized)
            if key not in seen:
                seen.add(key)
                unique.append(normalized)
        return unique

    def create(self, directory: str | os.PathLike[str], prefix: str = "backup_diario") -> str:
        target_dir = Path(directory).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = self.now()
        stem = f"{self._safe_prefix(prefix)}_{timestamp:%Y%m%d_%H%M%S_%f}"
        sequence = 0
        while True:
            suffix = "" if sequence == 0 else f"_{sequence}"
            target = target_dir / f"{stem}{suffix}.db"
            try:
                descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                sequence += 1
                continue
            os.close(descriptor)
            break
        try:
            backup_database(self.database_path, target)
            self._validate(target)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return str(target)

    def create_encrypted(
        self,
        directory: str | os.PathLike[str],
        password: str,
        prefix: str = "backup_manual",
    ) -> str:
        """Cria envelope autenticado sem persistir a senha ou alterar o formato legado."""

        target_dir = Path(directory).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{self._safe_prefix(prefix)}_{self.now():%Y%m%d_%H%M%S_%f}"
        sequence = 0
        while True:
            suffix = "" if sequence == 0 else f"_{sequence}"
            target = target_dir / f"{stem}{suffix}.nabibackup"
            try:
                descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                sequence += 1
                continue
            os.close(descriptor)
            break
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        with tempfile.TemporaryDirectory(prefix="nabicode_backup_encrypt_") as temp_dir:
            plain = Path(temp_dir) / "database.db"
            try:
                backup_database(self.database_path, plain)
                self._validate(plain)
                encrypt_database(plain, temporary, password)
                self._verify_encrypted_to_temporary(temporary, password)
                temporary.replace(target)
            except Exception:
                temporary.unlink(missing_ok=True)
                target.unlink(missing_ok=True)
                raise
        return str(target)

    @staticmethod
    def inspect_backup(backup_path: str | os.PathLike[str]) -> BackupEnvelopeInfo:
        source = Path(backup_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError("Backup não encontrado.")
        return inspect_envelope(source)

    def create_all(self, prefix: str) -> BackupResult:
        created: list[str] = []
        fiscal_archives: list[str] = []
        errors: list[str] = []
        destinations: list[BackupDestinationResult] = []
        for directory in self.configured_directories():
            try:
                database_backup = self.create(directory, prefix)
                created.append(database_backup)
                archive = self.create_fiscal_archive(
                    directory, prefix=Path(database_backup).stem
                )
                if archive:
                    fiscal_archives.append(archive)
                destinations.append(BackupDestinationResult(
                    directory, True, database_backup=database_backup,
                    fiscal_archive=archive,
                ))
            except Exception as exc:  # erro por destino deve ser reportado sem abortar os demais
                errors.append(f"{directory}: {exc}")
                destinations.append(
                    BackupDestinationResult(directory, False, error=str(exc))
                )
        return BackupResult(
            tuple(created), tuple(errors), fiscal_archives=tuple(fiscal_archives),
            destinations=tuple(destinations),
        )

    def create_fiscal_archive(
        self, directory: str | os.PathLike[str], *, prefix: str
    ) -> str:
        if self.fiscal_directory is None or not self.fiscal_directory.is_dir():
            return ""
        files = [
            path for path in self.fiscal_directory.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".xml", ".pdf"}
            and not set(
                part.casefold() for part in path.relative_to(self.fiscal_directory).parts
            ).intersection({"certificate", "email"})
        ]
        if not files:
            return ""
        target_dir = Path(directory).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{self._safe_prefix(prefix)}_fiscal.zip"
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        manifest: list[dict[str, object]] = []
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(files):
                    relative = path.relative_to(self.fiscal_directory).as_posix()
                    data = path.read_bytes()
                    manifest.append({
                        "path": relative, "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    })
                    archive.writestr(f"documents/{relative}", data)
                archive.writestr(
                    "manifest.json",
                    json.dumps({
                        "version": 1,
                        "created_at": self.now().isoformat(timespec="seconds"),
                        "retain_until": (self.now() + timedelta(days=1827)).date().isoformat(),
                        "documents": manifest,
                    }, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                )
            self._validate_fiscal_archive(temporary)
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return str(target)

    def restore_fiscal_archive(
        self, archive_path: str | os.PathLike[str],
        target_directory: str | os.PathLike[str] | None = None,
    ) -> tuple[str, ...]:
        archive_path = Path(archive_path).resolve()
        manifest = self._validate_fiscal_archive(archive_path)
        target = Path(target_directory).resolve() if target_directory else self.fiscal_directory
        if target is None:
            raise ValueError("A pasta fiscal de restauração não foi configurada.")
        planned: list[tuple[Path, bytes]] = []
        with zipfile.ZipFile(archive_path) as archive:
            for item in manifest["documents"]:
                relative = Path(str(item["path"]))
                destination = (target / relative).resolve()
                if target != destination and target not in destination.parents:
                    raise ValueError("O pacote fiscal contém caminho inseguro.")
                data = archive.read(f"documents/{relative.as_posix()}")
                if destination.exists():
                    if hashlib.sha256(destination.read_bytes()).hexdigest() != item["sha256"]:
                        raise FileExistsError(
                            f"Já existe documento fiscal diferente em {relative.as_posix()}."
                        )
                    continue
                planned.append((destination, data))
        restored: list[str] = []
        for destination, data in planned:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
            temporary.write_bytes(data)
            temporary.replace(destination)
            restored.append(str(destination))
        return tuple(restored)

    @staticmethod
    def _validate_fiscal_archive(path: Path) -> dict:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError("Arquivo de guarda fiscal ausente ou vazio.")
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                raise ValueError("Pacote fiscal sem manifesto.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("version") != 1 or not isinstance(manifest.get("documents"), list):
                raise ValueError("Manifesto do pacote fiscal é inválido.")
            for item in manifest["documents"]:
                relative = Path(str(item.get("path") or ""))
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Pacote fiscal contém caminho inseguro.")
                name = f"documents/{relative.as_posix()}"
                if name not in names:
                    raise ValueError(f"Documento ausente no pacote fiscal: {relative}.")
                data = archive.read(name)
                if len(data) != int(item.get("size") or -1):
                    raise ValueError(f"Tamanho divergente no pacote fiscal: {relative}.")
                if hashlib.sha256(data).hexdigest() != item.get("sha256"):
                    raise ValueError(f"Hash divergente no pacote fiscal: {relative}.")
        return manifest

    def run_daily(self) -> BackupResult:
        with self._daily_lock:
            if self.get_config("backup_diario_ativo") != "1":
                return BackupResult((), (), skipped=True)
            today = self.now().strftime("%Y-%m-%d")
            directories = self.configured_directories()
            destination_results: list[BackupDestinationResult] = []
            created: list[str] = []
            fiscal_archives: list[str] = []
            errors: list[str] = []
            for directory in directories:
                state_key = self._daily_destination_key(directory)
                if self.get_config(state_key) == today:
                    destination_results.append(
                        BackupDestinationResult(directory, True, skipped=True)
                    )
                    continue
                try:
                    database_backup = self.create(directory, "backup_diario")
                    archive = self.create_fiscal_archive(
                        directory, prefix=Path(database_backup).stem
                    )
                    self.set_config(state_key, today)
                    created.append(database_backup)
                    if archive:
                        fiscal_archives.append(archive)
                    destination_results.append(BackupDestinationResult(
                        directory, True, database_backup=database_backup,
                        fiscal_archive=archive,
                    ))
                except Exception as exc:
                    message = f"{directory}: {exc}"
                    errors.append(message)
                    destination_results.append(
                        BackupDestinationResult(directory, False, error=str(exc))
                    )
            if directories and not errors and all(item.succeeded for item in destination_results):
                self.set_config("ultimo_backup_diario", today)
            skipped = bool(destination_results) and all(item.skipped for item in destination_results)
            return BackupResult(
                tuple(created), tuple(errors), skipped=skipped,
                fiscal_archives=tuple(fiscal_archives),
                destinations=tuple(destination_results),
            )

    @staticmethod
    def _daily_destination_key(directory: str) -> str:
        normalized = os.path.normcase(str(Path(directory).expanduser().resolve()))
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
        return f"ultimo_backup_diario_destino_{digest}"

    def verify_restore_in_temporary(
        self, backup_path: str | os.PathLike[str], password: str | None = None
    ) -> RestoreVerificationResult:
        """Prova a restauração numa base descartável; nunca toca no banco ativo."""

        source = Path(backup_path).expanduser().resolve()
        info = inspect_envelope(source)
        with tempfile.TemporaryDirectory(prefix="nabicode_restore_check_") as temporary:
            restored = Path(temporary) / "restored.db"
            if info.encrypted:
                if password is None:
                    raise ValueError("Informe a senha do backup criptografado.")
                decrypt_database(source, restored, password)
            else:
                self._validate(source)
                backup_database(source, restored)
            self._validate(restored)
            connection = open_connection(restored, apply_journal=False)
            try:
                integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
                foreign_keys = tuple(
                    tuple(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()
                )
                table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'"
                ).fetchone()
                version_row = connection.execute(
                    "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
                ).fetchone() if table else None
                try:
                    schema_version = int(version_row[0]) if version_row else 0
                except (TypeError, ValueError):
                    schema_version = 0
            finally:
                connection.close()
            active = open_connection(self.database_path, apply_journal=False)
            try:
                active_table = active.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'"
                ).fetchone()
                active_row = active.execute(
                    "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
                ).fetchone() if active_table else None
                try:
                    active_schema = int(active_row[0]) if active_row else 0
                except (TypeError, ValueError):
                    active_schema = 0
            finally:
                active.close()
            if schema_version != active_schema:
                raise RuntimeError(
                    "Backup incompatível com a versão atual do banco: "
                    f"backup={schema_version}; atual={active_schema}."
                )
        return RestoreVerificationResult(
            str(source), file_sha256(source), integrity, foreign_keys, schema_version,
            info.format, info.encrypted,
        )

    def _verify_encrypted_to_temporary(self, source: Path, password: str) -> None:
        with tempfile.TemporaryDirectory(prefix="nabicode_backup_verify_") as temporary:
            restored = Path(temporary) / "restored.db"
            decrypt_database(source, restored, password)
            self._validate(restored)

    @staticmethod
    def _safe_prefix(prefix: str) -> str:
        cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in str(prefix).strip())
        return cleaned or "backup"

    @staticmethod
    def _validate(path: Path) -> None:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError("Backup inválido: arquivo ausente ou vazio")
        conn = open_connection(path, apply_journal=False)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                raise RuntimeError(f"Backup inválido: integrity_check={integrity!r}")
            foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_keys:
                raise RuntimeError(f"Backup inválido: {len(foreign_keys)} violação(ões) de chave estrangeira")
        finally:
            conn.close()
