from __future__ import annotations

import gc
import json
import sqlite3
import tempfile
import time
import tracemalloc
from pathlib import Path


def test_five_thousand_connection_cycles():
    cycles = 5000
    committed = 0
    rolled_back = 0
    samples = []
    started = time.perf_counter()
    tracemalloc.start()
    with tempfile.TemporaryDirectory() as temporary:
        database_path = Path(temporary) / "soak.db"
        connection = sqlite3.connect(database_path)
        connection.execute("CREATE TABLE eventos(id INTEGER PRIMARY KEY, ciclo INTEGER UNIQUE, estado TEXT)")
        connection.commit()
        connection.close()

        for cycle in range(1, cycles + 1):
            connection = sqlite3.connect(database_path, timeout=5)
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO eventos(ciclo,estado) VALUES(?,?)",
                    (cycle, "COMMIT" if cycle % 5 == 0 else "ROLLBACK"),
                )
                assert connection.execute("SELECT COUNT(*) FROM eventos").fetchone()[0] >= 1
                if cycle % 5 == 0:
                    connection.commit()
                    committed += 1
                else:
                    connection.rollback()
                    rolled_back += 1
            finally:
                connection.close()
            if cycle % 1000 == 0:
                gc.collect()
                samples.append(tracemalloc.get_traced_memory()[0])

        connection = sqlite3.connect(database_path, timeout=5)
        try:
            assert connection.execute("SELECT COUNT(*) FROM eventos").fetchone()[0] == committed
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
        finally:
            connection.close()

        current_memory, peak_memory = tracemalloc.get_traced_memory()
        metrics = {
            "cycles": cycles,
            "commits": committed,
            "rollbacks": rolled_back,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "memory_samples_bytes": samples,
            "memory_current_bytes": current_memory,
            "memory_peak_bytes": peak_memory,
            "database_bytes": database_path.stat().st_size,
        }
        print("SOAK_METRICS=" + json.dumps(metrics, sort_keys=True))
    tracemalloc.stop()
