from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from database import DatabaseManager
from helpers.file_hashing import sha256_file


class SystemSnapshotService:
    """Cria, valida, lista e restaura snapshots verificáveis do banco SQLite."""

    def __init__(
        self,
        database: DatabaseManager,
        *,
        rollback_dir: str | os.PathLike[str],
        update_state_file: str | os.PathLike[str],
        app_version: str,
        schema_version: int,
    ) -> None:
        self.database = database
        self.rollback_dir = Path(rollback_dir).expanduser().resolve()
        self.update_state_file = Path(update_state_file).expanduser().resolve()
        self.app_version = str(app_version)
        self.schema_version = int(schema_version)

    @staticmethod
    def _now_id() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    @staticmethod
    def _atomic_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    _sha256 = staticmethod(sha256_file)

    @staticmethod
    def _safe_reason(reason: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(reason or "")).strip("_")
        return normalized or "snapshot"

    @staticmethod
    def _integrity(path: Path) -> bool:
        connection = sqlite3.connect(str(path), timeout=30)
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            return bool(row and row[0] == "ok")
        finally:
            connection.close()

    def create(self, reason: str = "manual") -> dict[str, Any]:
        source_path = self.database.database_path
        if not source_path.is_file():
            raise FileNotFoundError(f"Banco de dados não encontrado: {source_path}")

        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        identifier = f"{self._now_id()}_{self._safe_reason(reason)}"
        folder = self.rollback_dir / identifier
        folder.mkdir(parents=False, exist_ok=False)
        destination_path = folder / "banco.db"

        with self.database.session() as source:
            destination = sqlite3.connect(str(destination_path), timeout=60)
            try:
                source.backup(destination)
                row = destination.execute("PRAGMA integrity_check").fetchone()
                if not row or row[0] != "ok":
                    raise sqlite3.DatabaseError(f"Snapshot inválido: {row}")
            finally:
                destination.close()

        manifest: dict[str, Any] = {
            "id": identifier,
            "data": datetime.now().isoformat(timespec="seconds"),
            "motivo": reason,
            "versao_app": self.app_version,
            "versao_schema": self.schema_version,
            "banco_origem": str(source_path),
            "banco_snapshot": str(destination_path),
            "sha256": self._sha256(destination_path),
            "tamanho": destination_path.stat().st_size,
            "computador": socket.gethostname(),
        }
        self._atomic_json(folder / "manifesto.json", manifest)
        return manifest

    def list(self) -> list[dict[str, Any]]:
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        snapshots: list[dict[str, Any]] = []
        for folder in sorted(self.rollback_dir.iterdir(), reverse=True):
            manifest_path = folder / "manifesto.json"
            database_path = folder / "banco.db"
            if not folder.is_dir() or not manifest_path.is_file() or not database_path.is_file():
                continue
            try:
                with manifest_path.open("r", encoding="utf-8") as stream:
                    data = json.load(stream)
                if not isinstance(data, dict):
                    raise ValueError("Manifesto inválido: objeto JSON esperado.")
                data["pasta"] = str(folder)
                data["valido"] = (
                    data.get("sha256") == self._sha256(database_path)
                    and self._integrity(database_path)
                )
                snapshots.append(data)
            except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
                snapshots.append({"id": folder.name, "pasta": str(folder), "valido": False, "erro": str(exc)})
        return snapshots

    def restore(self, snapshot_id: str) -> dict[str, Any]:
        snapshots = {item.get("id"): item for item in self.list()}
        item = snapshots.get(snapshot_id)
        if not item:
            raise FileNotFoundError("Snapshot não encontrado.")
        if not item.get("valido"):
            raise ValueError("O snapshot selecionado não passou na validação de integridade.")

        safety = self.create("antes_do_rollback")
        source_path = Path(str(item["pasta"])) / "banco.db"
        temporary_path = self.database.database_path.with_name(self.database.database_path.name + ".restauracao.tmp")
        try:
            shutil.copy2(source_path, temporary_path)
            if not self._integrity(temporary_path):
                raise sqlite3.DatabaseError("Banco restaurado falhou na verificação de integridade.")
            os.replace(temporary_path, self.database.database_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        self._atomic_json(
            self.update_state_file,
            {
                "ultima_acao": "rollback",
                "data": datetime.now().isoformat(timespec="seconds"),
                "snapshot_restaurado": snapshot_id,
                "snapshot_seguranca": safety["id"],
                "versao_app": self.app_version,
            },
        )
        return safety
