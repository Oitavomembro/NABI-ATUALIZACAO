from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from database.sqlite_connection import backup_database, open_connection


@dataclass(frozen=True)
class BackupResult:
    created: tuple[str, ...]
    errors: tuple[str, ...]
    skipped: bool = False


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
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.database_path = Path(database_path)
        self.default_directory = Path(default_directory)
        self.get_config = get_config
        self.set_config = set_config
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

    def create_all(self, prefix: str) -> BackupResult:
        created: list[str] = []
        errors: list[str] = []
        for directory in self.configured_directories():
            try:
                created.append(self.create(directory, prefix))
            except Exception as exc:  # erro por destino deve ser reportado sem abortar os demais
                errors.append(f"{directory}: {exc}")
        return BackupResult(tuple(created), tuple(errors))

    def run_daily(self) -> BackupResult:
        with self._daily_lock:
            if self.get_config("backup_diario_ativo") != "1":
                return BackupResult((), (), skipped=True)
            today = self.now().strftime("%Y-%m-%d")
            if self.get_config("ultimo_backup_diario") == today:
                return BackupResult((), (), skipped=True)
            result = self.create_all("backup_diario")
            if result.created:
                self.set_config("ultimo_backup_diario", today)
            return result

    @staticmethod
    def _safe_prefix(prefix: str) -> str:
        cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in str(prefix).strip())
        return cleaned or "backup"

    @staticmethod
    def _validate(path: Path) -> None:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError("Backup invÃ¡lido: arquivo ausente ou vazio")
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
