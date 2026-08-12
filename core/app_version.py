"""Carregamento resiliente da versão da aplicação.

O executável não pode deixar de iniciar apenas porque ``VERSAO.txt`` não foi
copiado pelo empacotador. O arquivo continua sendo a fonte preferencial, mas a
versão compilada funciona como fallback seguro e auditável.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable

_VERSION_RE = re.compile(r"^(?:v\s*)?(\d+)\.(\d+)\.(\d+)$", re.IGNORECASE)


def normalize_app_version(value: object) -> str | None:
    """Normaliza versões no formato ``X.Y.Z`` e aceita BOM/prefixo ``v``."""

    if value is None:
        return None
    text = str(value).lstrip("\ufeff").strip()
    match = _VERSION_RE.fullmatch(text)
    if not match:
        return None
    return ".".join(match.groups())


def _unique_paths(paths: Iterable[Path | None]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if path is None:
            continue
        try:
            normalized = Path(path).expanduser().resolve(strict=False)
        except (OSError, RuntimeError, TypeError, ValueError):
            continue
        key = os.path.normcase(str(normalized))
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return tuple(result)


def version_file_candidates(
    *,
    source_file: str | os.PathLike[str] | None = None,
    executable: str | os.PathLike[str] | None = None,
    runtime_dir: str | os.PathLike[str] | None = None,
    explicit_path: str | os.PathLike[str] | None = None,
) -> tuple[Path, ...]:
    """Retorna candidatos válidos para ``VERSAO.txt`` em fonte e PyInstaller."""

    source_path = Path(source_file) if source_file else Path(__file__)
    executable_path = Path(executable) if executable else Path(sys.executable)
    pyinstaller_dir = runtime_dir or getattr(sys, "_MEIPASS", None)
    env_path = os.environ.get("NABICODE_VERSION_FILE")

    return _unique_paths(
        (
            Path(explicit_path) if explicit_path else None,
            Path(env_path) if env_path else None,
            executable_path.parent / "VERSAO.txt",
            source_path.resolve(strict=False).parent / "VERSAO.txt",
            source_path.resolve(strict=False).parent.parent / "VERSAO.txt",
            Path(pyinstaller_dir) / "VERSAO.txt" if pyinstaller_dir else None,
        )
    )


def load_app_version(
    fallback: str,
    *,
    source_file: str | os.PathLike[str] | None = None,
    executable: str | os.PathLike[str] | None = None,
    runtime_dir: str | os.PathLike[str] | None = None,
    explicit_path: str | os.PathLike[str] | None = None,
) -> str:
    """Carrega a versão sem impedir a inicialização do executável.

    ``fallback`` representa a versão incorporada ao código no momento do build.
    Ele é usado somente quando nenhum arquivo candidato contém uma versão válida.
    """

    normalized_fallback = normalize_app_version(fallback)
    if normalized_fallback is None:
        raise ValueError(f"Fallback de versão inválido: {fallback!r}")

    for path in version_file_candidates(
        source_file=source_file,
        executable=executable,
        runtime_dir=runtime_dir,
        explicit_path=explicit_path,
    ):
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        normalized = normalize_app_version(content)
        if normalized is not None:
            return normalized

    return normalized_fallback
