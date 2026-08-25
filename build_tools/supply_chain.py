from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from packaging.utils import canonicalize_name, parse_wheel_filename


_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)$")
_HASH_RE = re.compile(r"^\s+--hash=sha256:([0-9a-f]{64})$")


class SupplyChainError(ValueError):
    pass


@dataclass(frozen=True)
class LockedArtifact:
    name: str
    version: str
    sha256: str
    filename: str


def read_locked_artifacts(lock_path: Path) -> tuple[LockedArtifact, ...]:
    lines = lock_path.read_text(encoding="utf-8").splitlines()
    artifacts: list[LockedArtifact] = []
    names: set[str] = set()
    approved_filename: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if line.startswith("# artifact: "):
            if approved_filename is not None:
                raise SupplyChainError("entrada de artefato sem pacote correspondente")
            approved_filename = line.removeprefix("# artifact: ").strip()
            if not approved_filename or Path(approved_filename).name != approved_filename:
                raise SupplyChainError("nome de artefato inseguro no lock")
            continue
        if not line or line.startswith("#"):
            continue
        if approved_filename is None:
            raise SupplyChainError(f"artefato aprovado ausente antes de {line!r}")
        if not line.endswith("\\") or line.endswith("\\\\"):
            raise SupplyChainError(f"continuação inválida no lock: {line!r}")
        match = _PIN_RE.fullmatch(line[:-1].rstrip())
        if not match:
            raise SupplyChainError(f"linha de pacote inválida no lock: {line!r}")
        if index >= len(lines):
            raise SupplyChainError(f"hash ausente para {match.group(1)}")
        hash_match = _HASH_RE.fullmatch(lines[index])
        index += 1
        if not hash_match:
            raise SupplyChainError(f"exatamente um hash SHA-256 é obrigatório para {match.group(1)}")
        canonical_name = canonicalize_name(match.group(1))
        if canonical_name in names:
            raise SupplyChainError(f"pacote duplicado no lock: {match.group(1)}")
        names.add(canonical_name)
        artifacts.append(LockedArtifact(canonical_name, match.group(2), hash_match.group(1), approved_filename))
        approved_filename = None
    if approved_filename is not None:
        raise SupplyChainError("entrada de artefato sem pacote correspondente")
    if not artifacts:
        raise SupplyChainError("lock vazio")
    return tuple(artifacts)


def validate_wheelhouse(lock_path: Path, wheelhouse: Path) -> tuple[Path, ...]:
    locked = read_locked_artifacts(lock_path)
    wheels = tuple(sorted(wheelhouse.glob("*.whl"), key=lambda item: item.name.casefold()))
    by_identity: dict[tuple[str, str], list[Path]] = {}
    for wheel in wheels:
        try:
            name, version, _build, _tags = parse_wheel_filename(wheel.name)
        except ValueError as exc:
            raise SupplyChainError(f"wheel inválido: {wheel.name}") from exc
        by_identity.setdefault((canonicalize_name(name), str(version)), []).append(wheel)

    approved: list[Path] = []
    expected_identities = {(item.name, item.version) for item in locked}
    extras = sorted(
        wheel.name
        for identity, candidates in by_identity.items()
        if identity not in expected_identities
        for wheel in candidates
    )
    if extras:
        raise SupplyChainError(f"wheel extra não aprovado: {', '.join(extras)}")

    for item in locked:
        candidates = by_identity.get((item.name, item.version), [])
        if len(candidates) != 1:
            raise SupplyChainError(
                f"{item.name}=={item.version} exige exatamente um wheel; encontrados: {len(candidates)}"
            )
        wheel = candidates[0]
        if wheel.name != item.filename:
            raise SupplyChainError(f"wheel diferente do artefato aprovado: {wheel.name}")
        actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if actual != item.sha256:
            raise SupplyChainError(f"hash divergente: {wheel.name}")
        approved.append(wheel)
    return tuple(approved)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Valida o lock e o wheelhouse aprovados.")
    parser.add_argument("lock", type=Path)
    parser.add_argument("wheelhouse", type=Path)
    args = parser.parse_args()
    validate_wheelhouse(args.lock, args.wheelhouse)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
