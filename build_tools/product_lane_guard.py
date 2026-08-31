from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping


RUNTIME_SUFFIXES = frozenset({".py", ".json", ".qss", ".ico", ".png", ".svg"})


def tree_digest(root: Path, relative_path: str) -> str:
    """Hash both the inventory and contents of one product source tree."""
    target = root / relative_path
    if not target.exists():
        return "AUSENTE"
    if target.is_file():
        files = [target]
    else:
        files = sorted(
            path
            for path in target.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in RUNTIME_SUFFIXES
            and "__pycache__" not in path.parts
        )

    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        contents = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def validate_product_lane(
    root: Path,
    *,
    product: str,
    expected_digests: Mapping[str, str],
) -> None:
    changed = [
        relative_path
        for relative_path, expected in expected_digests.items()
        if tree_digest(root, relative_path) != expected
    ]
    if changed:
        paths = ", ".join(changed)
        raise RuntimeError(
            f"Trilha do produto {product} divergente em: {paths}. "
            "Build bloqueado para impedir mistura entre edicoes. "
            "Revise a alteracao e atualize o contrato somente se ela pertencer "
            "deliberadamente a este produto."
        )
