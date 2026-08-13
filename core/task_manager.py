from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .event_bus import EventBus


class TaskStatus(str, Enum):
    PENDING = "PENDENTE"
    RUNNING = "EXECUTANDO"
    COMPLETED = "CONCLUIDA"
    FAILED = "FALHOU"
    CANCELLED = "CANCELADA"


class TaskCancelledError(RuntimeError):
    pass


@dataclass
class TaskContext:
    task_id: str
    _cancel_event: threading.Event
    _progress_callback: Callable[[float, str], None]

    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def check_cancelled(self) -> None:
        if self.cancelled():
            raise TaskCancelledError("Tarefa cancelada pelo usuário.")

    def report_progress(self, value: float, message: str = "") -> None:
        self.check_cancelled()
        normalized = max(0.0, min(1.0, float(value)))
        self._progress_callback(normalized, str(message or ""))


@dataclass
class TaskRecord:
    id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    _cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _future: Future | None = field(default=None, repr=False)

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at or time.time()
        start = self.started_at or self.created_at
        return max(0.0, end - start)


TaskFunction = Callable[[TaskContext], Any]


class TaskManager:
    """Executor de tarefas em segundo plano com progresso, cancelamento e eventos."""

    def __init__(
        self,
        max_workers: int = 2,
        max_records: int = 200,
        event_bus: EventBus | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers deve ser maior que zero.")
        if max_records < 1:
            raise ValueError("max_records deve ser maior que zero.")
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="NabiCodeTask")
        self._event_bus = event_bus
        self._logger = logger or logging.getLogger("NabiCode.TaskManager")
        self._records: dict[str, TaskRecord] = {}
        self._max_records = int(max_records)
        self._lock = threading.RLock()
        self._shutdown = False

    def submit(self, name: str, function: TaskFunction) -> TaskRecord:
        if not name.strip() or not callable(function):
            raise ValueError("Nome e função válidos são obrigatórios.")
        with self._lock:
            if self._shutdown:
                raise RuntimeError("O gerenciador de tarefas já foi encerrado.")
            self._prune_finished_locked()
            task_id = uuid.uuid4().hex
            record = TaskRecord(id=task_id, name=name.strip())
            self._records[task_id] = record
            record._future = self._executor.submit(self._run, record, function)
        self._publish("tarefa.criada", record)
        return record

    def _run(self, record: TaskRecord, function: TaskFunction) -> None:
        with self._lock:
            if record._cancel_event.is_set():
                record.status = TaskStatus.CANCELLED
                record.finished_at = time.time()
                self._publish("tarefa.cancelada", record)
                return
            record.status = TaskStatus.RUNNING
            record.started_at = time.time()
        self._publish("tarefa.iniciada", record)

        def update_progress(value: float, message: str) -> None:
            with self._lock:
                record.progress = value
                record.message = message
            self._publish("tarefa.progresso", record)

        context = TaskContext(record.id, record._cancel_event, update_progress)
        try:
            result = function(context)
            context.check_cancelled()
            with self._lock:
                record.result = result
                record.progress = 1.0
                record.status = TaskStatus.COMPLETED
                record.finished_at = time.time()
            self._publish("tarefa.concluida", record)
        except TaskCancelledError as exc:
            with self._lock:
                record.status = TaskStatus.CANCELLED
                record.error = str(exc)
                record.finished_at = time.time()
            self._publish("tarefa.cancelada", record)
        except Exception as exc:
            self._logger.exception("Falha na tarefa '%s' (%s)", record.name, record.id)
            with self._lock:
                record.status = TaskStatus.FAILED
                record.error = str(exc)
                record.finished_at = time.time()
            self._publish("tarefa.falhou", record)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            record = self._records.get(task_id)
            if record is None or record.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                return False
            record._cancel_event.set()
            if record._future and record._future.cancel():
                record.status = TaskStatus.CANCELLED
                record.finished_at = time.time()
                self._publish("tarefa.cancelada", record)
            return True

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._records.get(task_id)

    def list(self, active_only: bool = False) -> list[TaskRecord]:
        with self._lock:
            records = list(self._records.values())
        if active_only:
            records = [item for item in records if item.status in {TaskStatus.PENDING, TaskStatus.RUNNING}]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def _prune_finished_locked(self) -> None:
        overflow = len(self._records) - self._max_records + 1
        if overflow <= 0:
            return
        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        finished = sorted(
            (item for item in self._records.values() if item.status in terminal),
            key=lambda item: item.finished_at or item.created_at,
        )
        for record in finished[:overflow]:
            self._records.pop(record.id, None)

    def wait(self, task_id: str, timeout: float | None = None) -> TaskRecord:
        record = self.get(task_id)
        if record is None:
            raise KeyError(f"Tarefa não encontrada: {task_id}")
        if record._future:
            record._future.result(timeout=timeout)
        return record

    def shutdown(self, wait: bool = True, cancel_pending: bool = False) -> None:
        with self._lock:
            self._shutdown = True
            if cancel_pending:
                for record in self._records.values():
                    if record.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                        record._cancel_event.set()
        self._executor.shutdown(wait=wait, cancel_futures=cancel_pending)

    def _publish(self, event: str, record: TaskRecord) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            event,
            task_id=record.id,
            nome=record.name,
            status=record.status.value,
            progresso=record.progress,
            mensagem=record.message,
            erro=record.error,
            duracao=record.elapsed_seconds,
        )
