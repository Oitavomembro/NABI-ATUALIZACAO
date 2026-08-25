from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from build_tools.supply_chain import SupplyChainError, read_locked_artifacts, validate_wheelhouse


def _wheel(root: Path, name: str, content: bytes = b"wheel") -> tuple[Path, str]:
    path = root / name
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


def _lock(root: Path, *entries: tuple[str, str, str]) -> Path:
    path = root / "requirements.lock"
    path.write_text(
        "# Python 3.14 Windows x64\n"
        + "".join(f"# artifact: {name.replace('-', '_')}-{version}-py3-none-any.whl\n{name}=={version} \\\n    --hash=sha256:{digest}\n" for name, version, digest in entries),
        encoding="utf-8",
    )
    return path


def test_accepts_exactly_one_preapproved_wheel_per_locked_entry(tmp_path: Path) -> None:
    wheel, digest = _wheel(tmp_path, "demo_pkg-1.2.3-py3-none-any.whl")
    lock = _lock(tmp_path, ("demo-pkg", "1.2.3", digest))

    assert validate_wheelhouse(lock, tmp_path) == (wheel,)


@pytest.mark.parametrize("failure", ["missing", "extra", "duplicate", "tampered"])
def test_wheelhouse_fails_closed_for_non_exact_catalog(tmp_path: Path, failure: str) -> None:
    wheel, digest = _wheel(tmp_path, "demo_pkg-1.2.3-py3-none-any.whl")
    lock = _lock(tmp_path, ("demo-pkg", "1.2.3", digest))
    if failure == "missing":
        wheel.unlink()
    elif failure == "extra":
        _wheel(tmp_path, "other-1.0-py3-none-any.whl")
    elif failure == "duplicate":
        _wheel(tmp_path, "demo_pkg-1.2.3-1-py3-none-any.whl")
    else:
        wheel.write_bytes(b"alterado")

    with pytest.raises(SupplyChainError):
        validate_wheelhouse(lock, tmp_path)


def test_lock_rejects_ranges_missing_hashes_and_multiple_hashes(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("# artifact: demo-1-py3-none-any.whl\ndemo>=1\n", encoding="utf-8")
    with pytest.raises(SupplyChainError):
        read_locked_artifacts(lock)

    lock.write_text("# artifact: demo-1-py3-none-any.whl\ndemo==1 \\\n    --hash=sha256:" + "a" * 64 + "\n    --hash=sha256:" + "b" * 64 + "\n", encoding="utf-8")
    with pytest.raises(SupplyChainError):
        read_locked_artifacts(lock)
