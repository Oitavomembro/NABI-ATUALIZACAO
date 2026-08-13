from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

EventHandler = Callable[..., Any]


@dataclass(frozen=True)
class EventSubscription:
    event: str
    token: int


class EventBus:
    """Barramento de eventos síncrono, seguro para threads e isolado de falhas."""

    def __init__(self, logger: logging.Logger | None = None):
        self._handlers: dict[str, dict[int, EventHandler]] = defaultdict(dict)
        self._lock = threading.RLock()
        self._next_token = 1
        self._logger = logger or logging.getLogger("NabiCode.EventBus")

    def subscribe(self, event: str, handler: EventHandler) -> EventSubscription:
        event = self._event_name(event)
        if not callable(handler):
            raise ValueError("Evento e manipulador válidos são obrigatórios.")
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._handlers[event][token] = handler
            return EventSubscription(event, token)

    def unsubscribe(self, subscription: EventSubscription) -> bool:
        with self._lock:
            handlers = self._handlers.get(subscription.event)
            if not handlers or subscription.token not in handlers:
                return False
            del handlers[subscription.token]
            if not handlers:
                self._handlers.pop(subscription.event, None)
            return True

    def publish(self, event: str, **payload: Any) -> list[Any]:
        event = self._event_name(event)
        with self._lock:
            handlers = list(self._handlers.get(event, {}).values())
        results: list[Any] = []
        for handler in handlers:
            try:
                results.append(handler(**payload))
            except Exception:
                self._logger.exception("Falha no evento '%s' em %r", event, handler)
        return results

    def clear(self, event: str | None = None) -> None:
        with self._lock:
            if event is None:
                self._handlers.clear()
            else:
                event = self._event_name(event)
                self._handlers.pop(event, None)

    @staticmethod
    def _event_name(event: str) -> str:
        normalized = str(event or "").strip()
        if not normalized:
            raise ValueError("O nome do evento não pode ser vazio.")
        return normalized
