from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import main as startup_main
from core.runtime_profile import DatabaseInUseError, DatabaseUsageLock
from core.startup_window_coordinator import (
    SPLASH_PAUSE_ENV,
    prepare_startup_modal,
    reset_startup_modal_state_for_tests,
    startup_modal_scope,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
SPLASH_SOURCE = (ROOT / "splash_screen.py").read_text(encoding="utf-8")
LEGACY_SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class _FakeWindow:
    def __init__(self):
        self.calls = []

    def transient(self, parent):
        self.calls.append(("transient", parent))

    def grab_set(self):
        self.calls.append(("grab_set",))

    def lift(self):
        self.calls.append(("lift",))

    def focus_force(self):
        self.calls.append(("focus_force",))


class Checkpoint35StartupSplashTests(unittest.TestCase):
    def tearDown(self):
        reset_startup_modal_state_for_tests()
        os.environ.pop(SPLASH_PAUSE_ENV, None)

    def test_01_second_instance_lock_still_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "nabicode.db"
            first = DatabaseUsageLock(database, "PRODUCAO")
            second = DatabaseUsageLock(database, "PRODUCAO")
            first.acquire()
            try:
                with self.assertRaises(DatabaseInUseError):
                    second.acquire()
            finally:
                first.release()

    def test_02_instance_conflict_has_controlled_user_flow(self):
        message = startup_main._instance_conflict_message("PRODUCAO")
        self.assertIn("NabiCode já está aberto", message)
        self.assertIn("banco de PRODUÇÃO", message)
        self.assertIn("except DatabaseInUseError", MAIN_SOURCE)
        conflict_block = MAIN_SOURCE.split("except DatabaseInUseError", 1)[1].split("except Exception", 1)[0]
        self.assertIn("return 0", conflict_block)
        self.assertNotIn("raise", conflict_block)

    def test_03_required_modal_has_explicit_parent_and_focus(self):
        parent = object()
        window = _FakeWindow()
        prepare_startup_modal(window, parent)
        self.assertEqual(window.calls[0], ("transient", parent))
        self.assertIn(("grab_set",), window.calls)
        self.assertIn(("lift",), window.calls)
        self.assertIn(("focus_force",), window.calls)

    def test_04_splash_pause_is_nested_and_restored(self):
        with tempfile.TemporaryDirectory() as folder:
            pause = Path(folder) / "splash.pause"
            os.environ[SPLASH_PAUSE_ENV] = str(pause)
            with startup_modal_scope():
                self.assertTrue(pause.exists())
                with startup_modal_scope():
                    self.assertTrue(pause.exists())
                self.assertTrue(pause.exists())
            self.assertFalse(pause.exists())

    def test_05_cancelled_initial_setup_does_not_leave_pause_signal(self):
        with tempfile.TemporaryDirectory() as folder:
            pause = Path(folder) / "splash.pause"
            os.environ[SPLASH_PAUSE_ENV] = str(pause)

            def cancelled_flow():
                with startup_modal_scope():
                    self.assertTrue(pause.exists())
                    return False

            self.assertFalse(cancelled_flow())
            self.assertFalse(pause.exists())
            self.assertIn("with startup_modal_scope():", LEGACY_SOURCE)

    def test_06_startup_error_requests_splash_shutdown(self):
        with tempfile.TemporaryDirectory() as folder:
            stop = Path(folder) / "splash.stop"
            startup_main._stop_splash(stop)
            self.assertTrue(stop.exists())
        error_block = MAIN_SOURCE.split("except DatabaseInUseError", 1)[1].split(
            "except Exception as exc:", 1
        )[1].split("finally:", 1)[0]
        self.assertIn("_pause_splash(pause_file)", error_block)
        self.assertIn("_stop_splash(stop_file)", error_block)

    def test_07_lock_is_released_by_finally(self):
        final_block = MAIN_SOURCE.split('mark_startup("shutdown_started")', 1)[1]
        self.assertIn("database_lock.release()", final_block)
        self.assertIn("_ensure_process_stopped(splash_process, timeout=2.0)", final_block)

    def test_08_splash_coordination_does_not_change_runtime_profile(self):
        previous_profile = os.environ.get("NABICODE_PROFILE")
        previous_app_dir = os.environ.get("NABICODE_APP_DIR")
        with tempfile.TemporaryDirectory() as folder:
            os.environ[SPLASH_PAUSE_ENV] = str(Path(folder) / "pause")
            with startup_modal_scope():
                pass
        self.assertEqual(os.environ.get("NABICODE_PROFILE"), previous_profile)
        self.assertEqual(os.environ.get("NABICODE_APP_DIR"), previous_app_dir)

    def test_09_splash_has_no_database_or_business_dependency(self):
        self.assertNotIn("sqlite3", SPLASH_SOURCE)
        self.assertNotIn("nabicode_legacy", SPLASH_SOURCE)
        self.assertNotIn("repositories", SPLASH_SOURCE)
        self.assertNotIn("services.finance", SPLASH_SOURCE)
        self.assertNotIn("NABICODE_PROFILE", SPLASH_SOURCE)

    def test_10_splash_uses_canonical_pygame_only_in_the_helper_process(self):
        self.assertNotIn("time.sleep", SPLASH_SOURCE)
        self.assertNotIn("while True", SPLASH_SOURCE)
        self.assertIn("import splash_deep_trust_engine", SPLASH_SOURCE)
        self.assertIn("self.clock.tick(self.engine.FPS)", SPLASH_SOURCE)
        self.assertIn("self.pygame.event.get()", SPLASH_SOURCE)
        self.assertNotIn("from PIL", SPLASH_SOURCE)


if __name__ == "__main__":
    unittest.main()
