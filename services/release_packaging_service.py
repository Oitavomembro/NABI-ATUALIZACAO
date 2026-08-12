from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SensitivePackageFinding:
    path: str
    reason: str


class ReleasePackagingService:
    """Valida que pacotes de código não carreguem dados operacionais ou segredos."""

    BLOCKED_SUFFIXES = {
        ".db", ".sqlite", ".sqlite3", ".pfx", ".p12", ".pem", ".key",
        ".crt", ".cer", ".env", ".bak", ".backup",
    }
    BLOCKED_NAMES = {".env", "credentials.json", "secrets.json"}
    BLOCKED_DIRS = {
        "backups", "backup", "backups_moveis",
        "certificados", "certificates", "secrets",
    }

    @classmethod
    def inspect_paths(cls, paths: Iterable[Path], *, root: Path) -> tuple[SensitivePackageFinding, ...]:
        findings: list[SensitivePackageFinding] = []
        for path in paths:
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            parts = {part.casefold() for part in relative.parts[:-1]}
            name = relative.name.casefold()
            suffix = relative.suffix.casefold()
            reason = ""
            if name in cls.BLOCKED_NAMES or suffix in cls.BLOCKED_SUFFIXES:
                reason = "extensão ou nome sensível"
            elif parts & cls.BLOCKED_DIRS:
                reason = "diretório de dados ou backup"
            if reason:
                findings.append(SensitivePackageFinding(relative.as_posix(), reason))
        return tuple(findings)

    @classmethod
    def validate_tree(cls, root: Path) -> None:
        findings = cls.inspect_paths(root.rglob("*"), root=root)
        if findings:
            details = "\n".join(f"- {item.path}: {item.reason}" for item in findings)
            raise ValueError(f"Pacote contém arquivos sensíveis proibidos:\n{details}")
