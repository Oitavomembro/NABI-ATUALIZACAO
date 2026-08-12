from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from helpers.file_hashing import sha256_file
from services.release_packaging_service import ReleasePackagingService


class ReleasePackageController:
    def __init__(
        self,
        project_dir: str | Path,
        version: str,
        *,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.version = str(version).strip()
        self.clock = clock

    def locate_release(self) -> Path:
        dist = self.project_dir / "dist"
        candidates = [dist / f"NabiCode_v{self.version.replace('.', '_')}", dist / "NabiCode"]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        folders = [item for item in dist.glob("*") if item.is_dir()] if dist.is_dir() else []
        if len(folders) == 1:
            return folders[0]
        raise FileNotFoundError("Pasta compilada não encontrada em dist. Gere o EXE final primeiro.")

    def create(
        self,
        *,
        minimum_source: str,
        accepted_sources: Iterable[str] = (),
        remove: Iterable[str] = (),
    ) -> Path:
        release = self.locate_release()
        output = self.project_dir / f"NabiCode_ATUALIZACAO_{self.version.replace('.', '_')}.zip"
        files = [path for path in release.rglob("*") if path.is_file()]
        ReleasePackagingService.validate_tree(release)
        if not files:
            raise ValueError("A pasta compilada está vazia.")
        manifest_files = [
            {
                "path": path.relative_to(release).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
            for path in files
        ]
        normalized_sources = [str(item) for item in accepted_sources]
        manifest = {
            "product": "NabiCode",
            "package_type": "release",
            "version": self.version,
            "minimum_source_version": minimum_source,
            "accepted_source_versions": normalized_sources or [minimum_source],
            "created_at": self.clock().isoformat(timespec="seconds"),
            "files": manifest_files,
            "remove": list(remove),
        }
        with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path in files:
                archive.write(path, f"payload/{path.relative_to(release).as_posix()}")
        with ZipFile(output, "r") as archive:
            if bad := archive.testzip():
                raise RuntimeError(f"Pacote corrompido: {bad}")
        return output
