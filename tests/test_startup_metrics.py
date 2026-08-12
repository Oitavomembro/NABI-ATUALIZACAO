from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.startup_metrics import StartupMetrics


class StartupMetricsTests(unittest.TestCase):
    def test_disabled_metrics_do_not_write_files(self) -> None:
        metrics = StartupMetrics()
        metrics.mark("ignored")
        self.assertFalse(metrics.enabled)
        self.assertEqual(metrics.snapshot()["events"], [])

    def test_enabled_metrics_write_ordered_atomic_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "startup.json"
            metrics = StartupMetrics(output)
            metrics.mark("runtime_profile_ready", profile="TESTE")
            metrics.mark("database_lock_acquired")
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(
            [event["name"] for event in payload["events"]],
            ["runtime_profile_ready", "database_lock_acquired"],
        )
        self.assertEqual(payload["events"][0]["details"]["profile"], "TESTE")
        self.assertGreaterEqual(payload["events"][1]["elapsed_ms"], payload["events"][0]["elapsed_ms"])
        self.assertGreaterEqual(payload["events"][1]["delta_ms"], 0)


if __name__ == "__main__":
    unittest.main()
