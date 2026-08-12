from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True)
class DatabaseCheckReport:
    database_path: str
    checked_at: str
    integrity: str
    foreign_key_errors: tuple[tuple, ...]
    schema_version: int
    expected_schema_version: int | None
    missing_tables: tuple[str, ...]
    page_count: int
    freelist_count: int
    file_size: int

    @property
    def valid(self) -> bool:
        schema_ok = self.expected_schema_version is None or self.schema_version == self.expected_schema_version
        return self.integrity == "ok" and not self.foreign_key_errors and not self.missing_tables and schema_ok

    def to_dict(self) -> dict:
        data = asdict(self)
        data["valid"] = self.valid
        return data


@dataclass(frozen=True)
class Migration:
    version: int
    apply: Callable[[sqlite3.Connection], None]
    description: str = ""


class DatabaseMaintenanceService:
    """Operações verificáveis de manutenção SQLite sem depender da interface gráfica."""

    def __init__(
        self,
        database_path: str | os.PathLike[str],
        backup_directory: str | os.PathLike[str],
        *,
        expected_schema_version: int | None = None,
        required_tables: Iterable[str] = (),
        timeout: float = 60,
    ) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.backup_directory = Path(backup_directory).expanduser().resolve()
        self.expected_schema_version = expected_schema_version
        self.required_tables = tuple(dict.fromkeys(str(name) for name in required_tables if str(name).strip()))
        self.timeout = float(timeout)

    def _connect(self, path: Path | None = None) -> sqlite3.Connection:
        connection = sqlite3.connect(str(path or self.database_path), timeout=self.timeout)
        connection.execute(f"PRAGMA busy_timeout={int(self.timeout * 1000)}")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _schema_version(connection: sqlite3.Connection) -> int:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'"
        ).fetchone()
        if not table:
            return 0
        row = connection.execute(
            "SELECT valor FROM configuracoes WHERE chave='db_schema_version' LIMIT 1"
        ).fetchone()
        try:
            return int(row[0]) if row else 0
        except (TypeError, ValueError):
            return 0

    def check(self, path: str | os.PathLike[str] | None = None) -> DatabaseCheckReport:
        target = Path(path).expanduser().resolve() if path else self.database_path
        if not target.is_file():
            raise FileNotFoundError(f"Banco não encontrado: {target}")
        connection = self._connect(target)
        try:
            integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
            integrity = "\n".join(str(row[0]) for row in integrity_rows) or "sem resultado"
            fk_errors = tuple(tuple(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall())
            existing = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            missing = tuple(name for name in self.required_tables if name not in existing)
            page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
            freelist_count = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
            schema_version = self._schema_version(connection)
        finally:
            connection.close()
        return DatabaseCheckReport(
            database_path=str(target),
            checked_at=datetime.now().isoformat(timespec="seconds"),
            integrity=integrity,
            foreign_key_errors=fk_errors,
            schema_version=schema_version,
            expected_schema_version=self.expected_schema_version,
            missing_tables=missing,
            page_count=page_count,
            freelist_count=freelist_count,
            file_size=target.stat().st_size,
        )

    def create_backup(self, *, prefix: str = "backup", validate: bool = True) -> tuple[Path, DatabaseCheckReport]:
        if not self.database_path.is_file():
            raise FileNotFoundError(f"Banco não encontrado: {self.database_path}")
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        destination = self.backup_directory / f"{prefix}_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
        source = self._connect()
        copy: sqlite3.Connection | None = None
        try:
            copy = self._connect(destination)
            source.execute("PRAGMA wal_checkpoint(PASSIVE)")
            source.backup(copy)
            copy.commit()
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            if copy is not None:
                copy.close()
            source.close()
        report = self.check(destination)
        if validate and not report.valid:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"Backup rejeitado pela validação: {report.to_dict()}")
        return destination, report

    def restore(self, backup_path: str | os.PathLike[str]) -> tuple[Path, DatabaseCheckReport]:
        source_path = Path(backup_path).expanduser().resolve()
        candidate = self.check(source_path)
        if not candidate.valid:
            raise RuntimeError(f"Backup inválido para restauração: {candidate.to_dict()}")

        safety_path, _ = self.create_backup(prefix="antes_restauracao", validate=True)
        source = self._connect(source_path)
        target: sqlite3.Connection | None = None
        try:
            target = self._connect()
            source.backup(target)
            target.commit()
        except Exception:
            if target is not None:
                target.close()
            source.close()
            # Restaura imediatamente a cópia de segurança se a operação falhar no meio.
            rollback_source = self._connect(safety_path)
            rollback_target: sqlite3.Connection | None = None
            try:
                rollback_target = self._connect()
                rollback_source.backup(rollback_target)
                rollback_target.commit()
            finally:
                if rollback_target is not None:
                    rollback_target.close()
                rollback_source.close()
            raise
        else:
            target.close()
            source.close()

        restored = self.check()
        if not restored.valid:
            rollback_source = self._connect(safety_path)
            rollback_target: sqlite3.Connection | None = None
            try:
                rollback_target = self._connect()
                rollback_source.backup(rollback_target)
                rollback_target.commit()
            finally:
                if rollback_target is not None:
                    rollback_target.close()
                rollback_source.close()
            raise RuntimeError("Restauração revertida porque o banco restaurado falhou na validação final.")
        return safety_path, restored

    def reindex(self) -> DatabaseCheckReport:
        connection = self._connect()
        try:
            connection.execute("REINDEX")
            connection.commit()
        finally:
            connection.close()
        return self.check()

    def compact(self) -> DatabaseCheckReport:
        connection = self._connect()
        try:
            connection.execute("VACUUM")
        finally:
            connection.close()
        return self.check()

    def export_report(self, destination: str | os.PathLike[str]) -> Path:
        path = Path(destination).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.check().to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
        return path

    def run_migrations(self, migrations: Iterable[Migration]) -> int:
        ordered = sorted(migrations, key=lambda migration: migration.version)
        connection = self._connect()
        try:
            current = self._schema_version(connection)
            for migration in ordered:
                if migration.version <= current:
                    continue
                connection.execute("BEGIN IMMEDIATE")
                try:
                    migration.apply(connection)
                    connection.execute(
                        "INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES('db_schema_version', ?)",
                        (str(migration.version),),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                current = migration.version
            return current
        finally:
            connection.close()
