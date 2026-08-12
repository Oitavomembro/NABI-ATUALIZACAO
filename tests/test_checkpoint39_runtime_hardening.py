from __future__ import annotations

import json
import gc
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
import unittest
from pathlib import Path
from unittest import mock

import core.runtime_profile as runtime_profile
from core.runtime_profile import DatabaseInUseError, DatabaseUsageLock
from database import DatabaseManager


ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
LEGACY_SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class DatabaseLockHardeningTests(unittest.TestCase):
    def lock(self, folder: str, profile: str = "PRODUCAO") -> DatabaseUsageLock:
        return DatabaseUsageLock(Path(folder) / "dados.db", profile)

    def write_owner(self, lock: DatabaseUsageLock, **overrides) -> None:
        payload = {
            "pid": 1234,
            "host": socket.gethostname(),
            "profile": "PRODUCAO",
            "database": str(lock.database_path),
            "owner_token": "anterior",
            "process_started_at": 100.0,
        }
        payload.update(overrides)
        lock.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock.lock_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_pid_reutilizado_nao_mantem_lock_orfao(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = self.lock(folder)
            self.write_owner(lock)
            with (
                mock.patch.object(DatabaseUsageLock, "_pid_alive", return_value=True),
                mock.patch.object(DatabaseUsageLock, "_process_started_at", return_value=200.0),
            ):
                lock.acquire()
            try:
                current = json.loads(lock.lock_path.read_text(encoding="utf-8"))
                self.assertEqual(current["owner_token"], lock._owner_token)
            finally:
                lock.release()

    def test_lock_antigo_sem_identidade_detecta_pid_criado_depois(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = self.lock(folder)
            self.write_owner(lock, process_started_at=None)
            os.utime(lock.lock_path, (100.0, 100.0))
            with (
                mock.patch.object(DatabaseUsageLock, "_pid_alive", return_value=True),
                mock.patch.object(DatabaseUsageLock, "_process_started_at", return_value=200.0),
            ):
                lock.acquire()
            lock.release()
            self.assertFalse(lock.lock_path.exists())

    def test_processo_vivo_com_mesma_identidade_continua_bloqueando(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = self.lock(folder)
            self.write_owner(lock, process_started_at=200.0)
            with (
                mock.patch.object(DatabaseUsageLock, "_pid_alive", return_value=True),
                mock.patch.object(DatabaseUsageLock, "_process_started_at", return_value=200.5),
            ):
                with self.assertRaises(DatabaseInUseError):
                    lock.acquire()

    def test_release_exige_token_e_nao_apaga_lock_substituto(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = self.lock(folder)
            lock.acquire()
            replacement = json.loads(lock.lock_path.read_text(encoding="utf-8"))
            replacement["owner_token"] = "outra-instancia"
            lock.lock_path.write_text(json.dumps(replacement), encoding="utf-8")
            lock.release()
            self.assertTrue(lock.lock_path.exists())

    def test_falha_ao_gravar_lock_remove_arquivo_parcial(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = self.lock(folder)
            with mock.patch.object(runtime_profile.json, "dump", side_effect=OSError("disco")):
                with self.assertRaises(OSError):
                    lock.acquire()
            self.assertFalse(lock.lock_path.exists())

    def test_reinicio_rapido_nao_produz_falso_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            for _ in range(100):
                lock = self.lock(folder)
                lock.acquire()
                lock.release()
            self.assertFalse(lock.lock_path.exists())

    def test_corrida_local_tem_exatamente_um_vencedor(self):
        with tempfile.TemporaryDirectory() as folder:
            barrier = threading.Barrier(8)
            release = threading.Event()
            results: list[str] = []

            def contender() -> None:
                lock = self.lock(folder)
                barrier.wait()
                try:
                    lock.acquire()
                except DatabaseInUseError:
                    results.append("blocked")
                    return
                results.append("acquired")
                release.wait(2.0)
                lock.release()

            threads = [threading.Thread(target=contender) for _ in range(8)]
            for thread in threads:
                thread.start()
            deadline = time.monotonic() + 3.0
            while "acquired" not in results and time.monotonic() < deadline:
                time.sleep(0.01)
            release.set()
            for thread in threads:
                thread.join(3.0)
            self.assertEqual(results.count("acquired"), 1)
            self.assertEqual(results.count("blocked"), 7)

    def test_encerramento_abrupto_de_processo_deixa_lock_recuperavel(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "dados.db"
            ready = Path(folder) / "ready"
            code = (
                "import sys,time; from pathlib import Path; "
                "from core.runtime_profile import DatabaseUsageLock; "
                "lock=DatabaseUsageLock(sys.argv[1],'PRODUCAO'); lock.acquire(); "
                "Path(sys.argv[2]).touch(); time.sleep(60)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", code, str(database), str(ready)],
                cwd=str(ROOT),
            )
            try:
                deadline = time.monotonic() + 5.0
                while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists())
                with self.assertRaises(DatabaseInUseError):
                    self.lock(folder).acquire()
            finally:
                process.kill()
                process.wait(timeout=5.0)

            recovered = self.lock(folder)
            recovered.acquire()
            recovered.release()
            self.assertFalse(recovered.lock_path.exists())


class ProcessCleanupContractTests(unittest.TestCase):
    def test_timeout_final_do_helper_nao_interrompe_cleanup(self):
        import main

        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired("helper", 0.01)
        self.assertFalse(main._ensure_process_stopped(process, timeout=0.01))
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_count, 3)

    def test_runtime_tasks_shutdown_before_database_lock_release(self):
        final_block = MAIN_SOURCE.split('mark_startup("shutdown_started")', 1)[1]
        self.assertLess(
            final_block.index("shutdown_runtime_resources()"),
            final_block.index("database_lock.release()"),
        )
        shutdown = LEGACY_SOURCE.split("def shutdown_runtime_resources", 1)[1].split(
            "DATABASE_MANAGER", 1
        )[0]
        self.assertIn("TASK_MANAGER.shutdown(wait=True, cancel_pending=True)", shutdown)
        self.assertIn("if _RUNTIME_SHUTDOWN_DONE:", shutdown)


class ResourceSoakTests(unittest.TestCase):
    def test_three_thousand_connections_do_not_leak_fds_threads_or_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "resource_soak.db"
            manager = DatabaseManager(database_path)
            with manager.session(write=True) as connection:
                connection.execute("CREATE TABLE eventos(id INTEGER PRIMARY KEY, valor TEXT)")

            fd_dir = Path("/proc/self/fd")
            baseline_fds = len(list(fd_dir.iterdir())) if fd_dir.is_dir() else None
            baseline_threads = threading.active_count()
            samples: list[int] = []
            tracemalloc.start()
            try:
                for cycle in range(3000):
                    with manager.session(write=cycle % 10 == 0) as connection:
                        connection.execute("SELECT COUNT(*) FROM eventos").fetchone()
                        if cycle % 10 == 0:
                            connection.execute("INSERT INTO eventos(valor) VALUES(?)", (str(cycle),))
                    if cycle % 750 == 749:
                        gc.collect()
                        samples.append(tracemalloc.get_traced_memory()[0])
                current, _peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

            self.assertEqual(threading.active_count(), baseline_threads)
            if baseline_fds is not None:
                self.assertLessEqual(len(list(fd_dir.iterdir())), baseline_fds + 1)
            self.assertLess(current - samples[0], 512 * 1024)
            self.assertLess(max(samples) - min(samples), 512 * 1024)
            with manager.session() as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
