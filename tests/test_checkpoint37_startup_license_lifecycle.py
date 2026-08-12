from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main as startup_main
from splash_screen import DURATION, FPS, READY_HOLD_AT, LightspeedSplash


ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
SPLASH_SOURCE = (ROOT / "splash_screen.py").read_text(encoding="utf-8")
LEGACY_SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
SMOKE_VALIDATOR = (ROOT / "build_tools" / "build_windows.py").read_text(encoding="utf-8")


class _FakeProcess:
    def __init__(self):
        self.terminated = False
        self.wait_calls = 0

    def poll(self):
        return None if not self.terminated else 0

    def wait(self, timeout):
        self.wait_calls += 1
        if not self.terminated:
            raise subprocess.TimeoutExpired("splash", timeout)
        return 0

    def terminate(self):
        self.terminated = True


class _StubbornProcess:
    def __init__(self):
        self.killed = False
        self.wait_calls = 0

    def poll(self):
        return 0 if self.killed else None

    def wait(self, timeout):
        self.wait_calls += 1
        if not self.killed:
            raise subprocess.TimeoutExpired("splash", timeout)
        return 0

    def terminate(self):
        return None

    def kill(self):
        self.killed = True


class _UnreapableProcess:
    def __init__(self):
        self.wait_calls = 0

    def poll(self):
        return None

    def wait(self, timeout):
        self.wait_calls += 1
        raise subprocess.TimeoutExpired("splash", timeout)

    def terminate(self):
        return None

    def kill(self):
        return None


class Checkpoint37StartupLicenseLifecycleTests(unittest.TestCase):
    def test_01_timeline_preserves_canonical_prototype_times(self):
        self.assertEqual(FPS, 60)
        self.assertEqual(DURATION, 12.2)
        self.assertEqual(READY_HOLD_AT, 11.0)
        self.assertEqual(LightspeedSplash.timeline(2.0)[1], 0.0)
        self.assertEqual(LightspeedSplash.timeline(4.70)[3], 0.0)
        self.assertEqual(LightspeedSplash.timeline(7.55)[3], 1.0)
        self.assertEqual(LightspeedSplash.timeline(11.0)[0], 1.0)
        self.assertEqual(LightspeedSplash.timeline(12.2)[0], 0.0)

    def test_02_readiness_never_accelerates_sequence_and_late_readiness_resumes_fade(self):
        splash = LightspeedSplash.__new__(LightspeedSplash)
        splash.started_at = 0.0
        splash.ready_received_at = 2.0
        splash.ready_active_elapsed = 2.0
        self.assertEqual(splash._visual_elapsed(5.0), 5.0)
        self.assertEqual(splash._visual_elapsed(12.2), 12.2)

        splash.ready_received_at = None
        splash.ready_active_elapsed = None
        self.assertEqual(splash._visual_elapsed(30.0), 11.0)
        splash.ready_received_at = 30.0
        splash.ready_active_elapsed = 30.0
        self.assertAlmostEqual(splash._visual_elapsed(31.2), 12.2)

    def test_03_helper_loop_cannot_skip_cleanup_on_failure(self):
        self.assertIn("except Exception:", SPLASH_SOURCE)
        self.assertIn("self._record_error()", SPLASH_SOURCE)
        self.assertIn("finally:", SPLASH_SOURCE)
        self.assertIn("self._write_metrics()", SPLASH_SOURCE)
        self.assertIn("self.pygame.quit()", SPLASH_SOURCE)

    def test_04_splash_metrics_are_written_atomically_without_extra_text(self):
        with tempfile.TemporaryDirectory() as folder:
            metadata = Path(folder) / "metadata.json"
            splash = LightspeedSplash.__new__(LightspeedSplash)
            splash.metadata_file = metadata
            splash.engine = SimpleNamespace(W=1280, H=720)
            splash.display_width = 1280
            splash.display_height = 720
            splash.rendered_frames = 61
            splash.first_render_at = 10.0
            splash.last_render_completed_at = 11.0
            splash.total_render_seconds = 0.5
            splash.slowest_render_seconds = 0.02
            splash._write_metrics()
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(payload["measured_fps"], 60.0)
            self.assertNotIn("store_name", payload)
            self.assertEqual(startup_main._read_splash_metrics(metadata), payload)

    def test_05_main_window_readiness_precedes_splash_stop_and_reveal(self):
        reveal = MAIN_SOURCE.split("def reveal_application", 1)[1].split("app.after_idle", 1)[0]
        readiness = reveal.split("if readiness_signaled_at is None:", 1)[1]
        self.assertLess(reveal.index('"_main_window_ready"'), reveal.index("if readiness_signaled_at is None:"))
        self.assertLess(readiness.index("_stop_splash(stop_file)"), readiness.index("app.deiconify()"))
        self.assertIn('mark_startup("main_window_ready")', LEGACY_SOURCE)
        self.assertIn("self.after_idle(self._confirmar_main_window_ready)", LEGACY_SOURCE)

    def test_06_unresponsive_helper_is_terminated_and_reaped(self):
        process = _FakeProcess()
        startup_main._ensure_process_stopped(process, timeout=0.01)
        self.assertTrue(process.terminated)
        self.assertEqual(process.wait_calls, 2)

        stubborn = _StubbornProcess()
        startup_main._ensure_process_stopped(stubborn, timeout=0.01)
        self.assertTrue(stubborn.killed)
        self.assertEqual(stubborn.wait_calls, 3)

        unreapable = _UnreapableProcess()
        self.assertFalse(startup_main._ensure_process_stopped(unreapable, timeout=0.01))
        self.assertEqual(unreapable.wait_calls, 3)

    def test_07_license_dialog_uses_same_tk_root_without_nested_mainloop(self):
        block = LEGACY_SOURCE.split("def forcar_tela_bloqueio_inadimplencia", 1)[1].split(
            "def ativar_modo_panico", 1
        )[0]
        self.assertIn("ctk.CTkToplevel(self)", block)
        self.assertIn("self.wait_window(bloqueio_win)", block)
        self.assertNotIn("ctk.CTk()", block)
        self.assertNotIn("bloqueio_win.mainloop()", block)
        self.assertIn("grab_release()", block)

    def test_08_successful_unlock_restores_same_instance_and_clears_dialog_state(self):
        block = LEGACY_SOURCE.split("def forcar_tela_bloqueio_inadimplencia", 1)[1].split(
            "def ativar_modo_panico", 1
        )[0]
        self.assertIn("attempt_admin_unlock", block)
        self.assertIn('self._license_dialog_active = False', block)
        self.assertIn("self.deiconify()", block)
        self.assertIn('self.attributes("-alpha", 1.0)', block)
        self.assertIn("self.after(80, self.focus_force)", block)
        self.assertNotIn("raise SystemExit", block)
        self.assertIn("self.destroy()", block)

        monitor = LEGACY_SOURCE.split("def _monitorar_licenca", 1)[1].split(
            "def forcar_tela_bloqueio_inadimplencia", 1
        )[0]
        self.assertIn("self._servico_licenca().evaluate()", monitor)
        self.assertNotIn("monitor_exact_expiration()", monitor)

    def test_09_cash_opening_windows_use_shared_non_blocking_factory(self):
        question = LEGACY_SOURCE.split("def perguntar_abertura_caixa", 1)[1].split(
            "def abrir_formulario_abertura_caixa", 1
        )[0]
        form = LEGACY_SOURCE.split("def abrir_formulario_abertura_caixa", 1)[1].split(
            "def abrir_movimentacao_caixa", 1
        )[0]
        for block in (question, form):
            self.assertIn("_criar_modal_nabicode", block)
            self.assertIn("_mostrar_modal_nabicode", block)
            self.assertNotIn("reveal_prepared_toplevel_smooth", block)
            self.assertNotIn("reveal_prepared_toplevel_when_idle", block)
            self.assertNotIn("grab_set", block)
            self.assertNotIn('attributes("-alpha"', block)

    def test_10_normal_and_exception_paths_cleanup_all_splash_signals(self):
        self.assertIn("_cleanup_splash_files(stop_file, pause_file, metadata_file, splash_error_file)", MAIN_SOURCE)
        final_block = MAIN_SOURCE.split('mark_startup("shutdown_started")', 1)[1]
        self.assertIn("_pause_splash(pause_file)", final_block)
        self.assertIn("_stop_splash(stop_file)", final_block)
        self.assertIn("_ensure_process_stopped", final_block)

    def test_11_checkpoint36_smoke_contract_remains_intact(self):
        self.assertIn('"packaged_profile_resolved"', MAIN_SOURCE)
        self.assertIn('event.get("name") == "packaged_profile_resolved"', SMOKE_VALIDATOR)
        self.assertIn('"runtime_profile_ready",', SMOKE_VALIDATOR)

    def test_12_no_business_or_database_dependency_was_added_to_splash(self):
        for forbidden in ("sqlite3", "nabicode_legacy", "repositories", "PDVService", "FinanceiroService"):
            self.assertNotIn(forbidden, SPLASH_SOURCE)
        self.assertNotIn("time.sleep", SPLASH_SOURCE)
        self.assertNotIn("while True", SPLASH_SOURCE)


if __name__ == "__main__":
    unittest.main()
