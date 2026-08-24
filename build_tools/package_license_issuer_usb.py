"""Monta o pacote portátil do emissor sem transportar material secreto."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from importlib import metadata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE_NAME = "NabiCode_Emissor_Licencas_V2.exe"
MANUAL_NAME = "LEIA-ME-EMISSOR.txt"
HASHES_NAME = "SHA256SUMS.txt"
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".nabilic"}
RUNTIME_COMPONENTS = ("PySide6", "shiboken6", "cryptography")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_portable_directory(directory: Path) -> None:
    names = {path.name for path in directory.iterdir() if path.is_file()}
    expected = {EXECUTABLE_NAME, MANUAL_NAME, HASHES_NAME}
    if names != expected or any(path.is_dir() for path in directory.iterdir()):
        raise RuntimeError("A pasta portátil deve conter somente executável, manual e hashes.")
    offenders = [path for path in directory.rglob("*") if path.suffix.lower() in FORBIDDEN_SUFFIXES]
    if offenders:
        raise RuntimeError("Material secreto/licença encontrado no pacote portátil.")


def write_sbom(destination: Path) -> Path:
    components = [{
        "name": "Python",
        "version": sys.version.split()[0],
        "role": "runtime",
    }, {
        "name": "PyInstaller",
        "version": metadata.version("PyInstaller"),
        "role": "build",
    }]
    for name in RUNTIME_COMPONENTS:
        components.append({
            "name": name,
            "version": metadata.version(name),
            "role": "runtime",
        })
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({
        "schema": "nabicode-sbom-v1",
        "artifact": EXECUTABLE_NAME,
        "components": components,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def create_portable_package(executable: Path, destination: Path, manual: Path) -> Path:
    executable = executable.expanduser().resolve()
    destination = destination.expanduser().resolve()
    manual = manual.expanduser().resolve()
    if not executable.is_file() or executable.name != EXECUTABLE_NAME:
        raise FileNotFoundError("Executável administrativo não encontrado.")
    if not manual.is_file():
        raise FileNotFoundError("Manual operacional não encontrado.")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("A pasta portátil já existe e não será sobrescrita.")
    destination.mkdir(parents=True, exist_ok=True)
    target_executable = destination / EXECUTABLE_NAME
    target_manual = destination / MANUAL_NAME
    shutil.copy2(executable, target_executable)
    shutil.copy2(manual, target_manual)
    hashes = destination / HASHES_NAME
    hashes.write_text(
        f"{sha256(target_executable)}  {EXECUTABLE_NAME}\n"
        f"{sha256(target_manual)}  {MANUAL_NAME}\n",
        encoding="ascii",
    )
    validate_portable_directory(destination)
    return destination


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepara o Emissor NabiCode para pendrive")
    parser.add_argument(
        "--exe",
        default=str(PROJECT_ROOT / "build_output" / "license_issuer" / EXECUTABLE_NAME),
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "build_output" / "Emissor_NabiCode_Pendrive"),
    )
    options = parser.parse_args(argv)
    output = create_portable_package(
        Path(options.exe), Path(options.output), PROJECT_ROOT / "docs" / MANUAL_NAME
    )
    evidence = PROJECT_ROOT / "build_output" / "license_issuer" / "evidence"
    sbom = write_sbom(evidence / "SBOM.json")
    print(f"Pacote: {output}")
    print(f"SBOM: {sbom}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
