"""Instrumentação opt-in e sem dependências para o startup do NabiCode."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StartupMetrics:
    """Registra marcos monotônicos somente quando um destino foi configurado."""

    def __init__(self, output_path: str | os.PathLike[str] | None = None) -> None:
        self.output_path = Path(output_path).expanduser() if output_path else None
        self.started_at = time.perf_counter()
        self.started_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self._last_at = self.started_at
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    @classmethod
    def from_environment(cls) -> "StartupMetrics":
        return cls(os.environ.get("NABICODE_STARTUP_TRACE") or None)

    @property
    def enabled(self) -> bool:
        return self.output_path is not None

    def mark(self, name: str, **details: Any) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        with self._lock:
            event = {
                "name": str(name),
                "elapsed_ms": round((now - self.started_at) * 1000, 3),
                "delta_ms": round((now - self._last_at) * 1000, 3),
            }
            if details:
                event["details"] = details
            self._events.append(event)
            self._last_at = now
            self._write_snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "started_utc": self.started_utc,
            "pid": os.getpid(),
            "events": list(self._events),
        }

    def _write_snapshot(self) -> None:
        assert self.output_path is not None
        path = self.output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(self.snapshot(), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise


STARTUP_METRICS = StartupMetrics.from_environment()


def mark_startup(name: str, **details: Any) -> None:
    STARTUP_METRICS.mark(name, **details)
