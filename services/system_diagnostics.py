from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from database import DatabaseManager
from core.sensitive_data import sanitize


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    ok: bool
    detail: str
    severity: str = "error"


class SystemDiagnostics:
    """Executa verificações técnicas sem modificar dados de negócio."""

    def __init__(
        self,
        database: DatabaseManager,
        *,
        app_dir: str | os.PathLike[str],
        backup_dir: str | os.PathLike[str],
        rollback_dir: str | os.PathLike[str],
        diagnostic_dir: str | os.PathLike[str],
        app_version: str,
        schema_version: int,
        required_tables: Iterable[str] = (),
        minimum_free_mb: int = 200,
        max_backup_age_days: int = 7,
    ) -> None:
        self.database = database
        self.app_dir = Path(app_dir).expanduser().resolve()
        self.backup_dir = Path(backup_dir).expanduser().resolve()
        self.rollback_dir = Path(rollback_dir).expanduser().resolve()
        self.diagnostic_dir = Path(diagnostic_dir).expanduser().resolve()
        self.app_version = str(app_version)
        self.schema_version = int(schema_version)
        self.required_tables = frozenset(required_tables)
        self.minimum_free_mb = int(minimum_free_mb)
        self.max_backup_age_days = int(max_backup_age_days)

    def run(self, *, save_report: bool = True) -> dict:
        checks: list[DiagnosticCheck] = []
        self._check_paths(checks)
        self._check_database(checks)
        self._check_disk(checks)
        self._check_write_permissions(checks)
        self._check_backups(checks)

        approved = all(check.ok or check.severity == "warning" for check in checks)
        report = {
            "data": datetime.now().isoformat(timespec="seconds"),
            "versao_app": self.app_version,
            "schema": self.schema_version,
            "computador": socket.gethostname(),
            "banco": str(self.database.database_path),
            "aprovado": approved,
            "checks": [asdict(check) for check in checks],
        }
        if save_report:
            self.diagnostic_dir.mkdir(parents=True, exist_ok=True)
            target = self.diagnostic_dir / f"diagnostico_{datetime.now():%Y%m%d_%H%M%S_%f}.json"
            report = sanitize(report)
            self._write_json_atomic(target, report)
            report["arquivo"] = str(target)
        return sanitize(report)

    def _check_paths(self, checks: list[DiagnosticCheck]) -> None:
        checks.append(DiagnosticCheck("Pasta do aplicativo", self.app_dir.is_dir(), str(self.app_dir)))
        checks.append(DiagnosticCheck("Banco encontrado", self.database.database_path.is_file(), str(self.database.database_path)))
        checks.append(DiagnosticCheck("Pasta de backups", self.backup_dir.exists(), str(self.backup_dir), "warning"))

    def _check_database(self, checks: list[DiagnosticCheck]) -> None:
        if not self.database.database_path.is_file():
            return
        try:
            with self.database.session() as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                checks.append(DiagnosticCheck("Integridade SQLite", integrity == "ok", str(integrity)))

                fk_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
                checks.append(DiagnosticCheck("Chaves estrangeiras", not fk_errors, f"{len(fk_errors)} inconsistência(s)"))

                quick = connection.execute("PRAGMA quick_check").fetchone()[0]
                checks.append(DiagnosticCheck("Verificação rápida", quick == "ok", str(quick)))

                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
                missing = sorted(self.required_tables - tables)
                checks.append(DiagnosticCheck(
                    "Tabelas obrigatórias",
                    not missing,
                    "OK" if not missing else "Ausentes: " + ", ".join(missing),
                ))

                duplicate_indexes = connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND sql IS NOT NULL
                    GROUP BY tbl_name, sql HAVING COUNT(*) > 1
                    """
                ).fetchall()
                checks.append(DiagnosticCheck(
                    "Índices duplicados",
                    not duplicate_indexes,
                    "Nenhum" if not duplicate_indexes else f"{len(duplicate_indexes)} grupo(s)",
                    "warning",
                ))

                schema = self._read_schema_version(connection)
                checks.append(DiagnosticCheck(
                    "Versão do esquema",
                    str(schema) == str(self.schema_version),
                    f"Banco={schema}; esperado={self.schema_version}",
                ))
        except Exception as exc:
            checks.append(DiagnosticCheck("Acesso ao banco", False, str(exc)))

    @staticmethod
    def _read_schema_version(connection: sqlite3.Connection) -> str:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "configuracoes" not in tables:
            return "0"
        row = connection.execute(
            "SELECT valor FROM configuracoes WHERE chave='db_schema_version' LIMIT 1"
        ).fetchone()
        return str(row[0]) if row else "0"

    def _check_disk(self, checks: list[DiagnosticCheck]) -> None:
        try:
            usage = shutil.disk_usage(self.database.database_path.parent)
            free_mb = usage.free / (1024 * 1024)
            checks.append(DiagnosticCheck(
                "Espaço em disco",
                free_mb >= self.minimum_free_mb,
                f"{free_mb:,.0f} MB livres; mínimo={self.minimum_free_mb} MB",
            ))
        except Exception as exc:
            checks.append(DiagnosticCheck("Espaço em disco", False, str(exc)))

    def _check_write_permissions(self, checks: list[DiagnosticCheck]) -> None:
        for label, folder in (
            ("Aplicativo", self.app_dir),
            ("Backups", self.backup_dir),
            ("Rollback", self.rollback_dir),
            ("Diagnósticos", self.diagnostic_dir),
        ):
            try:
                folder.mkdir(parents=True, exist_ok=True)
                test_file = folder / ".nabicode_write_test.tmp"
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink()
                checks.append(DiagnosticCheck(f"Gravação: {label}", True, str(folder)))
            except Exception as exc:
                checks.append(DiagnosticCheck(f"Gravação: {label}", False, str(exc)))

    def _check_backups(self, checks: list[DiagnosticCheck]) -> None:
        candidates: list[Path] = []
        if self.backup_dir.is_dir():
            candidates.extend(path for path in self.backup_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".db")
        if self.rollback_dir.is_dir():
            candidates.extend(path for path in self.rollback_dir.rglob("banco.db") if path.is_file())
        if not candidates:
            checks.append(DiagnosticCheck("Backup recente", False, "Nenhum backup ou snapshot encontrado", "warning"))
            return
        latest = max(candidates, key=lambda path: path.stat().st_mtime)
        age_days = (datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)).days
        checks.append(DiagnosticCheck(
            "Backup recente",
            age_days <= self.max_backup_age_days,
            f"{latest.name} — {age_days} dia(s)",
            "warning",
        ))

    @staticmethod
    def format_report(report: dict) -> str:
        lines = [
            "DIAGNÓSTICO NABICODE",
            "=" * 72,
            f"Data: {report['data']}",
            f"Versão: {report['versao_app']} | Schema: {report['schema']}",
            f"Computador: {report['computador']}",
            f"Banco: {report['banco']}",
            "",
        ]
        for item in report["checks"]:
            status = "OK" if item["ok"] else ("AVISO" if item.get("severity") == "warning" else "FALHA")
            lines.append(f"{item['name']:.<34} {status}")
            lines.append(f"  {item['detail']}")
        lines.extend(["", "RESULTADO: " + ("SISTEMA APROVADO" if report["aprovado"] else "ATENÇÃO NECESSÁRIA")])
        return "\n".join(lines)

    @staticmethod
    def _write_json_atomic(path: Path, data: dict) -> None:
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
