from __future__ import annotations

import json
import os
import uuid
from pathlib import Path


class ProtectedStateStore:
    """Estado antifraude protegido pelo Windows e gravado atomicamente."""

    SCHEMA = 2

    def __init__(self, path: str | os.PathLike[str], protector) -> None:
        self.path = Path(path)
        self.protector = protector

    def read(self) -> dict:
        try:
            encrypted = self.path.read_bytes()
            raw = self.protector.unprotect(encrypted)
            value = json.loads(raw.decode("utf-8"))
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise ValueError("Estado protegido de licença inválido.") from exc
        if not isinstance(value, dict) or value.get("schema") != self.SCHEMA:
            raise ValueError("Estado protegido de licença incompatível.")
        return value

    def write(self, value: dict) -> None:
        payload = dict(value)
        payload["schema"] = self.SCHEMA
        raw = json.dumps(
            payload, ensure_ascii=True, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        encrypted = self.protector.protect(raw)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(encrypted)
            os.replace(temporary, self.path)
        finally:
            try:
                temporary.unlink()
            except OSError:
                pass


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
