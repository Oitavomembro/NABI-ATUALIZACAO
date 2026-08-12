import tempfile
import unittest
from pathlib import Path
from unittest import mock

import core.runtime_profile as runtime_profile
from core.runtime_profile import (
    DatabaseUsageLock,
    RuntimePaths,
    RuntimeProfile,
    resolve_profile_marker,
)


class RuntimeProfileTests(unittest.TestCase):
    def test_profile_marker_resolution_is_physical_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "PERFIL_NABICODE.txt"
            marker.write_text("PRODUCAO\n", encoding="utf-8")
            with mock.patch.dict(runtime_profile.os.environ, {"NABICODE_PROFILE": "TESTE"}):
                profile, resolved_marker = resolve_profile_marker(root)

            self.assertEqual(profile, "PRODUCAO")
            self.assertEqual(resolved_marker, marker.resolve())
            self.assertEqual(list(root.iterdir()), [marker])

    def test_all_mutable_paths_stay_under_profile_appdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            paths = RuntimePaths(root / "NabiCode" / "Producao")
            self.assertEqual(paths.database, paths.app_dir / "fichario_moveis.db")
            for path in paths.mutable_directories():
                self.assertTrue(path.is_relative_to(paths.app_dir), path)

    def test_program_directory_is_not_used_for_mutable_profile_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            program_files = root / "Program Files" / "NabiCode"
            profile = RuntimeProfile("PRODUCAO", root / "AppData" / "NabiCode" / "Producao")
            self.assertFalse(profile.paths.database.is_relative_to(program_files))
            self.assertTrue(profile.paths.database.is_relative_to(profile.app_dir.resolve()))

    def test_profile_marks_database_and_rejects_other_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "dados.db"
            prod = RuntimeProfile("PRODUCAO", root / "prod")
            teste = RuntimeProfile("TESTE", root / "teste")
            prod.validate_database(db)
            with self.assertRaises(RuntimeError):
                teste.validate_database(db)

    def test_lock_blocks_second_instance_and_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "dados.db"
            first = DatabaseUsageLock(db, "PRODUCAO")
            second = DatabaseUsageLock(db, "TESTE")
            try:
                first.acquire()
                with self.assertRaises(RuntimeError):
                    second.acquire()
                first.release()
                second.acquire()
            finally:
                second.release()
                first.release()

            self.assertFalse(first.lock_path.exists())

            # Mantém a contagem original da suíte e protege o mesmo cenário
            # contra a regressão que enviava CTRL_C_EVENT no Windows.
            with (
                mock.patch.object(runtime_profile, "_IS_WINDOWS", True),
                mock.patch.object(
                    DatabaseUsageLock,
                    "_windows_pid_alive",
                    return_value=True,
                ) as windows_probe,
                mock.patch.object(runtime_profile.os, "kill") as os_kill,
            ):
                self.assertTrue(DatabaseUsageLock._pid_alive(1234))

            windows_probe.assert_called_once_with(1234)
            os_kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
