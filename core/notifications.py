"""Notificações não bloqueantes e histórico em memória para a interface."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Deque, Iterable, Literal

NotificationLevel = Literal["success", "info", "warning", "error"]


@dataclass(frozen=True)
class NotificationRecord:
    title: str
    message: str
    level: NotificationLevel
    created_at: datetime
    duration_ms: int


class NotificationCenter:
    """Normaliza duração e mantém histórico limitado de notificações."""

    MIN_DURATION_MS = 1200
    MAX_DURATION_MS = 15000
    DEFAULT_DURATION_MS = 4200

    def __init__(self, *, max_history: int = 100, default_duration_ms: int = DEFAULT_DURATION_MS):
        if max_history < 1:
            raise ValueError("max_history deve ser maior que zero.")
        self._history: Deque[NotificationRecord] = deque(maxlen=int(max_history))
        self._lock = threading.RLock()
        self.default_duration_ms = self.normalize_duration(default_duration_ms)

    @classmethod
    def normalize_duration(cls, duration_ms: int | float | str | None) -> int:
        try:
            value = int(float(duration_ms))
        except (TypeError, ValueError):
            value = cls.DEFAULT_DURATION_MS
        return max(cls.MIN_DURATION_MS, min(cls.MAX_DURATION_MS, value))

    def publish(
        self,
        title: str,
        message: str,
        *,
        level: NotificationLevel = "info",
        duration_ms: int | None = None,
    ) -> NotificationRecord:
        normalized_level: NotificationLevel = level if level in {"success", "info", "warning", "error"} else "info"
        record = NotificationRecord(
            title=str(title or "Notificação").strip() or "Notificação",
            message=str(message or "").strip(),
            level=normalized_level,
            created_at=datetime.now(),
            duration_ms=self.normalize_duration(self.default_duration_ms if duration_ms is None else duration_ms),
        )
        with self._lock:
            self._history.appendleft(record)
        return record

    def set_default_duration(self, duration_ms: int | float | str | None) -> int:
        """Atualiza a duração padrão e retorna o valor normalizado."""
        with self._lock:
            self.default_duration_ms = self.normalize_duration(duration_ms)
            return self.default_duration_ms

    def history(self) -> list[NotificationRecord]:
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

    def extend(self, records: Iterable[NotificationRecord]) -> None:
        with self._lock:
            for record in records:
                self._history.append(record)
