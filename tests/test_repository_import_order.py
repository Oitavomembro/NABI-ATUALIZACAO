from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fresh_import(first: str, second: str) -> subprocess.CompletedProcess[str]:
    source = (
        "import sys; "
        f"sys.path.insert(0, {str(ROOT)!r}); "
        f"import {first}; import {second}; "
        "from repositories import EstoqueRepository; "
        "from services import EstoqueService; "
        "print(EstoqueRepository.__name__, EstoqueService.__name__)"
    )
    return subprocess.run(
        [sys.executable, "-I", "-c", source],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_repositories_then_services_import_in_fresh_interpreter() -> None:
    result = _fresh_import("repositories", "services")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "EstoqueRepository EstoqueService"


def test_services_then_repositories_import_in_fresh_interpreter() -> None:
    result = _fresh_import("services", "repositories")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "EstoqueRepository EstoqueService"
