from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_tools.package_license_issuer_usb import (
    EXECUTABLE_NAME, HASHES_NAME, MANUAL_NAME, create_portable_package,
    validate_portable_directory, write_sbom,
)


ROOT = Path(__file__).resolve().parents[1]


def test_machine_fingerprint_nao_importa_services() -> None:
    source = (ROOT / "licensing" / "machine.py").read_text(encoding="utf-8")
    assert "from services" not in source


def test_pacote_portatil_contem_somente_executavel_manual_e_hashes(tmp_path) -> None:
    executable = tmp_path / EXECUTABLE_NAME
    executable.write_bytes(b"MZ-emissor-teste")
    manual = tmp_path / "manual-fonte.txt"
    manual.write_text("Manual operacional", encoding="utf-8")
    output = create_portable_package(executable, tmp_path / "pendrive", manual)

    assert {path.name for path in output.iterdir()} == {
        EXECUTABLE_NAME, MANUAL_NAME, HASHES_NAME,
    }
    hashes = (output / HASHES_NAME).read_text(encoding="ascii")
    assert EXECUTABLE_NAME in hashes and MANUAL_NAME in hashes
    assert "PRIVATE KEY" not in b"".join(path.read_bytes() for path in output.iterdir()).decode(
        "utf-8", errors="ignore"
    )


def test_pacote_recusa_sobrescrita_e_material_secreto(tmp_path) -> None:
    executable = tmp_path / EXECUTABLE_NAME
    executable.write_bytes(b"MZ-emissor-teste")
    manual = tmp_path / "manual.txt"
    manual.write_text("Manual", encoding="utf-8")
    destination = tmp_path / "pendrive"
    destination.mkdir()
    (destination / "existente.txt").write_text("preservar", encoding="utf-8")
    with pytest.raises(FileExistsError):
        create_portable_package(executable, destination, manual)

    destination.joinpath("existente.txt").unlink()
    for name in (EXECUTABLE_NAME, MANUAL_NAME, HASHES_NAME):
        destination.joinpath(name).write_text("x", encoding="utf-8")
    destination.joinpath("segredo.pem").write_text("PRIVATE KEY", encoding="utf-8")
    with pytest.raises(RuntimeError, match="somente"):
        validate_portable_directory(destination)


def test_sbom_registra_componentes_sem_caminhos_ou_segredos(tmp_path) -> None:
    sbom = write_sbom(tmp_path / "SBOM.json")
    value = json.loads(sbom.read_text(encoding="utf-8"))
    names = {item["name"] for item in value["components"]}
    assert {"Python", "PyInstaller", "PySide6", "shiboken6", "cryptography"} <= names
    raw = sbom.read_text(encoding="utf-8")
    assert "NabiCode-Segredos" not in raw
    assert "PRIVATE KEY" not in raw
