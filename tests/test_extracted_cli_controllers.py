from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from controllers.developer_tools_controller import DeveloperToolsController
from controllers.release_package_controller import ReleasePackageController


def test_developer_tools_controller_creates_valid_backup(tmp_path: Path):
    database = tmp_path / "dados.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT)")
    connection.commit()
    connection.close()
    result = DeveloperToolsController(tmp_path).execute("backup", database_name=database.name)
    assert result.exit_code == 0
    assert "Integridade: ok" in result.text


def test_release_package_controller_builds_manifest(tmp_path: Path):
    release = tmp_path / "dist" / "NabiCode"
    release.mkdir(parents=True)
    (release / "main.exe").write_bytes(b"binary")
    controller = ReleasePackageController(
        tmp_path,
        "2.4.98",
        clock=lambda: datetime(2026, 8, 8, 12, 0, 0),
    )
    output = controller.create(minimum_source="2.4.97", revision=4)
    with ZipFile(output) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == "2.4.98"
        assert manifest["revision"] == 4
        assert manifest["accepted_source_versions"] == ["2.4.97"]
        assert archive.read("payload/main.exe") == b"binary"
    assert output.parent == tmp_path / "build_output" / "updates"
