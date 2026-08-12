from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
import zipfile


class UpdatePackageValidationService:
    def __init__(self, current_version: str) -> None:
        self.current_version = str(current_version).strip()

    @staticmethod
    def version_tuple(value: str) -> tuple[int, ...]:
        try:
            parts = tuple(int(part) for part in str(value).strip().split("."))
        except Exception as exc:
            raise ValueError("Versão inválida no pacote de atualização.") from exc
        if not parts:
            raise ValueError("Versão inválida no pacote de atualização.")
        return parts

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def validate(self, package_path: str | Path) -> dict[str, Any]:
        path = Path(package_path)
        if path.suffix.lower() != ".zip" or not path.is_file():
            raise ValueError("Selecione um pacote ZIP válido.")
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                raise ValueError("O pacote não contém manifest.json.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("product") != "NabiCode":
                raise ValueError("O pacote não pertence ao NabiCode.")
            target_version = str(manifest.get("version") or "").strip()
            minimum_version = str(manifest.get("minimum_source_version") or "").strip()
            accepted_sources = [
                str(item).strip()
                for item in (manifest.get("accepted_source_versions") or [])
                if str(item).strip()
            ]
            if not target_version:
                raise ValueError("O manifesto não informa a versão de destino.")
            if self.version_tuple(target_version) <= self.version_tuple(self.current_version):
                raise ValueError(
                    f"O pacote {target_version} não é mais novo que a versão instalada {self.current_version}."
                )
            if minimum_version and self.version_tuple(self.current_version) < self.version_tuple(minimum_version):
                raise ValueError(f"O pacote exige no mínimo a versão {minimum_version}.")
            if accepted_sources and self.current_version not in accepted_sources:
                raise ValueError(
                    f"Pacote incompatível com {self.current_version}. "
                    f"Origens aceitas: {', '.join(accepted_sources)}."
                )
            files = manifest.get("files") or []
            if not isinstance(files, list) or not files:
                raise ValueError("O manifesto não contém a lista de arquivos.")
            normalized: list[dict[str, Any]] = []
            for item in files:
                relative = str(item.get("path") or "").replace("\\", "/").lstrip("/")
                expected = str(item.get("sha256") or "").lower()
                zip_name = f"payload/{relative}"
                if not relative or ".." in Path(relative).parts or zip_name not in names:
                    raise ValueError(f"Arquivo inválido ou ausente no pacote: {relative or '<vazio>'}.")
                actual = self.sha256_bytes(archive.read(zip_name))
                if not expected or not hmac.compare_digest(actual, expected):
                    raise ValueError(f"SHA-256 inválido: {relative}.")
                normalized.append({**item, "path": relative, "sha256": expected})
            removed: list[str] = []
            for relative in manifest.get("remove") or []:
                normalized_path = str(relative).replace("\\", "/").lstrip("/")
                if not normalized_path or ".." in Path(normalized_path).parts:
                    raise ValueError(f"Caminho de remoção inválido: {relative}.")
                removed.append(normalized_path)
            manifest["files"] = normalized
            manifest["remove"] = removed
            return manifest
