import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StartupSmokeTestTests(unittest.TestCase):
    def test_source_startup_smoke_writes_loaded_version_without_opening_ui(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "version.txt"
            trace = Path(tmp) / "startup.json"
            appdata = Path(tmp) / "AppData"
            environment = dict(
                os.environ,
                APPDATA=str(appdata),
                NABICODE_STARTUP_TRACE=str(trace),
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "main.py"),
                    "--startup-smoke-test",
                    "--smoke-output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env=environment,
                timeout=20,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_text(encoding="utf-8").strip(), "2.5.2")
            events = json.loads(trace.read_text(encoding="utf-8"))["events"]
            self.assertEqual(
                [event["name"] for event in events],
                [
                    "process_imports_ready",
                    "main_entered",
                    "canonical_splash_engine_ready",
                    "packaged_profile_resolved",
                    "startup_smoke_complete",
                ],
            )
            self.assertEqual(events[2]["details"]["backend"], "pygame-ce")
            self.assertEqual(events[3]["details"]["profile"], "TESTE")
            self.assertFalse(appdata.exists())

    def test_all_build_scripts_execute_binary_smoke_test(self):
        for filename in ("GERAR_EXE_FINAL.bat", "GERAR_EXE_TESTE.bat", "GERAR_EXE_DEBUG.bat"):
            with self.subTest(filename=filename):
                source = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("--startup-smoke-test --smoke-output", source)
                self.assertIn("TESTE DE INICIALIZACAO DO EXE: OK", source)


if __name__ == "__main__":
    unittest.main()
