"""Gera o emissor externo sem incluir segredos nem módulos do NabiCode."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = PROJECT_ROOT / "build_tools" / "pyinstaller" / "nabicode_license_issuer.spec"
FORBIDDEN_SOURCE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".nabilic"}


def validate_emitter_source(root: Path = PROJECT_ROOT) -> None:
    offenders = [
        path for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in FORBIDDEN_SOURCE_SUFFIXES
        and ".git" not in path.parts
    ]
    if offenders:
        raise RuntimeError("Segredo/licença encontrado no checkout: " + ", ".join(map(str, offenders)))
    spec = SPEC.read_text(encoding="utf-8")
    if "datas=[]" not in spec.replace(" ", "") or "trusted_public_keys" in spec:
        raise RuntimeError("O spec do emissor não pode incorporar arquivos de chave ou dados do runtime.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build isolado do Emissor NabiCode V2")
    parser.add_argument("--dist", default=str(PROJECT_ROOT / "build_output" / "license_issuer"))
    options = parser.parse_args(argv)
    validate_emitter_source()
    destination = Path(options.dist).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(destination),
        "--workpath", str(destination / "_work"),
        str(SPEC),
    ]
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
