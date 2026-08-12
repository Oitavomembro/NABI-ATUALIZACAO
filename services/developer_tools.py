from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class DeveloperToolsService:
    """Ferramentas técnicas sem dependência da interface gráfica."""

    REQUIRED_PROJECT_FILES = (
        "VERSAO.txt",
        "main.py",
        "NabiCode.spec",
        "NabiCode.iss",
        "GERAR_EXE_DEBUG.bat",
        "GERAR_EXE_TESTE.bat",
        "GERAR_EXE_FINAL.bat",
        "GERAR_INSTALLADOR.bat",
        "EXECUTAR_TESTES.bat",
        "LIMPAR_BUILD.bat",
        "ATUALIZAR_DEPENDENCIAS.bat",
        "BACKUP_BANCO.bat",
        "requirements.txt",
    )

    def __init__(self, project_dir: str | os.PathLike[str], database_path: str | os.PathLike[str]) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.database_path = Path(database_path).resolve()

    @property
    def version(self) -> str:
        path = self.project_dir / "VERSAO.txt"
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise RuntimeError("VERSAO.txt está vazio.")
        return value

    def validate_tooling(self) -> dict[str, object]:
        missing = [name for name in self.REQUIRED_PROJECT_FILES if not (self.project_dir / name).is_file()]
        errors: list[str] = []
        try:
            version = self.version
        except (OSError, RuntimeError) as exc:
            version = ""
            errors.append(str(exc))
        if version and not all(part.isdigit() for part in version.split(".")):
            errors.append("VERSAO.txt deve conter apenas números separados por pontos.")

        tests_dir = self.project_dir / "tests"
        if not tests_dir.is_dir():
            missing.append("tests/")
        elif not any(tests_dir.glob("test_*.py")):
            errors.append("Nenhum teste test_*.py foi encontrado em tests/.")

        spec = self.project_dir / "NabiCode.spec"
        if spec.is_file():
            text = spec.read_text(encoding="utf-8", errors="replace")
            if "VERSAO.txt" not in text:
                errors.append("NabiCode.spec não inclui VERSAO.txt no pacote final.")

        return {
            "ok": not missing and not errors,
            "version": version or None,
            "missing": sorted(set(missing)),
            "errors": errors,
            "project_dir": str(self.project_dir),
        }

    def runtime_versions(self, packages: Iterable[str] = ("customtkinter", "pyinstaller")) -> dict[str, str]:
        result = {
            "nabicode": self.version,
            "python": platform.python_version(),
            "executavel_python": sys.executable,
            "sistema": platform.platform(),
        }
        for package in packages:
            try:
                result[package] = metadata.version(package)
            except metadata.PackageNotFoundError:
                result[package] = "não instalado"
        return result

    def run_tests(self) -> CommandResult:
        validation = self.validate_tooling()
        if not validation["ok"]:
            detail = json.dumps(validation, ensure_ascii=False, indent=2)
            return CommandResult((sys.executable, "-m", "unittest"), 2, "", detail)
        return self._run((sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"))

    def clean_build(self) -> list[str]:
        removed: list[str] = []
        for name in ("build", "dist"):
            path = self.project_dir / name
            if path.exists():
                shutil.rmtree(path)
                removed.append(str(path))
        for path in self.project_dir.rglob("__pycache__"):
            if path.is_dir():
                shutil.rmtree(path)
                removed.append(str(path))
        for path in self.project_dir.rglob("*.pyc"):
            if path.is_file():
                path.unlink()
                removed.append(str(path))
        return removed

    def export_diagnostic(self, destination_dir: str | os.PathLike[str]) -> Path:
        destination = Path(destination_dir).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = destination / f"diagnostico_nabicode_{stamp}.zip"
        manifest = {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "versoes": self.runtime_versions(),
            "projeto": str(self.project_dir),
            "banco": str(self.database_path),
            "banco_existe": self.database_path.is_file(),
            "ferramentas": self.validate_tooling(),
        }
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for relative in ("VERSAO.txt", "docs/CHANGELOG.md"):
                path = self.project_dir / relative
                if path.is_file():
                    package.write(path, relative)
            for folder_name in ("logs", "diagnosticos"):
                folder = self.project_dir / folder_name
                if folder.is_dir():
                    for path in folder.rglob("*"):
                        if path.is_file():
                            package.write(path, path.relative_to(self.project_dir))
        return archive

    def check_update(self, version_file: str | os.PathLike[str] | None = None) -> dict[str, object]:
        """Compara a versão local com um arquivo de versão informado.

        O projeto não possui endpoint oficial de atualização configurado; por isso a
        origem precisa ser fornecida explicitamente pelo chamador.
        """
        current = self.version
        if version_file is None:
            return {"current": current, "latest": None, "update_available": False, "configured": False}
        path = Path(version_file).resolve()
        latest = path.read_text(encoding="utf-8").strip()
        return {
            "current": current,
            "latest": latest,
            "update_available": self._version_key(latest) > self._version_key(current),
            "configured": True,
            "source": str(path),
        }

    def _run(self, command: tuple[str, ...]) -> CommandResult:
        completed = subprocess.run(
            command,
            cwd=self.project_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        return CommandResult(command, completed.returncode, completed.stdout, completed.stderr)

    @staticmethod
    def _version_key(value: str) -> tuple[int, ...]:
        parts: list[int] = []
        for item in value.strip().split("."):
            digits = "".join(character for character in item if character.isdigit())
            parts.append(int(digits or 0))
        return tuple(parts)
