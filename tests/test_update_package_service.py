import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from unittest import mock

from services.update_package_service import UpdatePackageService, _original_process_alive
from core.runtime_profile import DatabaseUsageLock


class UpdatePackageServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.install = self.root / "install"
        self.app = self.root / "appdata"
        self.install.mkdir()
        self.service = UpdatePackageService(app_dir=self.app, install_dir=self.install, current_version="2.4.37")

    def tearDown(self):
        self.temp.cleanup()

    def make_package(self, *, version="2.4.38", source="2.4.37", revision=0, files=None, remove=None):
        files = files or {"VERSAO.txt": version.encode(), "update_smoke_test.json": b'{"ok": true}'}
        manifest_files = [
            {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in files.items()
        ]
        manifest = {
            "product": "NabiCode",
            "version": version,
            "revision": revision,
            "minimum_source_version": source,
            "accepted_source_versions": [source],
            "files": manifest_files,
            "remove": remove or [],
        }
        package = self.root / "update.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            for name, data in files.items():
                archive.writestr(f"payload/{name}", data)
        return package

    def test_validates_version_source_and_hashes(self):
        package = self.make_package()
        manifest = self.service.validate(package)
        self.assertEqual(manifest["version"], "2.4.38")
        self.assertEqual(manifest["accepted_source_versions"], ["2.4.37"])

    def test_rejects_incompatible_source(self):
        package = self.make_package(source="2.4.36")
        with self.assertRaisesRegex(ValueError, "incompatível"):
            self.service.validate(package)

    def test_accepts_newer_revision_without_changing_semantic_version(self):
        (self.install / "REVISAO.txt").write_text("5\n", encoding="utf-8")
        service = UpdatePackageService(
            app_dir=self.app,
            install_dir=self.install,
            current_version="2.4.37",
        )
        package = self.make_package(version="2.4.37", revision=6)
        manifest = service.validate(package)
        self.assertEqual(manifest["revision"], 6)

    def test_rejects_same_or_older_revision(self):
        internal = self.install / "_internal"
        internal.mkdir()
        (internal / "REVISAO.txt").write_text("6\n", encoding="utf-8")
        service = UpdatePackageService(
            app_dir=self.app,
            install_dir=self.install,
            current_version="2.4.37",
        )
        package = self.make_package(version="2.4.37", revision=6)
        with self.assertRaisesRegex(ValueError, "não é mais novo"):
            service.validate(package)

    def test_prepare_backs_up_files_and_writes_state(self):
        (self.install / "VERSAO.txt").write_text("2.4.37", encoding="utf-8")
        package = self.make_package()
        manifest = self.service.validate(package)
        state = self.service.prepare(package, manifest, "snapshot-1")
        self.assertEqual(state["status"], "PREPARADO")
        self.assertIn("VERSAO.txt", state["backed_up"])
        self.assertIn("update_smoke_test.json", state["absent_before"])
        self.assertTrue(self.service.state_file.is_file())

    def test_validation_detects_changed_installed_file(self):
        package = self.make_package()
        manifest = self.service.validate(package)
        state = self.service.prepare(package, manifest, "snapshot-1")
        (self.install / "VERSAO.txt").write_text("errado", encoding="utf-8")
        (self.install / "update_smoke_test.json").write_text('{"ok": true}', encoding="utf-8")
        errors = self.service.validate_installed_files(state)
        self.assertTrue(any("VERSAO.txt" in error for error in errors))

    def test_restore_files_recovers_previous_state(self):
        (self.install / "VERSAO.txt").write_text("2.4.37", encoding="utf-8")
        package = self.make_package()
        manifest = self.service.validate(package)
        state = self.service.prepare(package, manifest, "snapshot-1")
        (self.install / "VERSAO.txt").write_text("2.4.38", encoding="utf-8")
        (self.install / "update_smoke_test.json").write_text("novo", encoding="utf-8")
        self.service.restore_files(state)
        self.assertEqual((self.install / "VERSAO.txt").read_text(encoding="utf-8"), "2.4.37")
        self.assertFalse((self.install / "update_smoke_test.json").exists())

    def test_update_helper_rejects_reused_pid_and_uses_safe_probe(self):
        with (
            mock.patch.object(DatabaseUsageLock, "_pid_alive", return_value=False),
            mock.patch.object(DatabaseUsageLock, "_process_started_at") as started,
        ):
            self.assertFalse(_original_process_alive(1234, 100.0))
            started.assert_not_called()

        with (
            mock.patch.object(DatabaseUsageLock, "_pid_alive", return_value=True),
            mock.patch.object(DatabaseUsageLock, "_process_started_at", return_value=200.0),
        ):
            self.assertFalse(_original_process_alive(1234, 100.0))
            self.assertTrue(_original_process_alive(1234, 200.5))

        with (
            mock.patch.object(DatabaseUsageLock, "_pid_alive", return_value=True),
            mock.patch.object(DatabaseUsageLock, "_process_started_at", return_value=None),
        ):
            self.assertTrue(_original_process_alive(1234, 100.0))


if __name__ == "__main__":
    unittest.main()
