from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import QMessageBox


class _BackupSignals(QObject):
    completed = Signal(object)
    failed = Signal(object)


class _DailyBackupWorker(QRunnable):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.signals = _BackupSignals()

    @Slot()
    def run(self):
        try:
            self.signals.completed.emit(self.service.run_daily())
        except Exception as error:
            self.signals.failed.emit(error)


class DailyBackupController(QObject):
    """Executa o backup depois do shell visível e publica somente resultado real."""

    def __init__(self, service, window, *, pool=None):
        super().__init__(window)
        self.service = service
        self.window = window
        self.pool = pool or QThreadPool.globalInstance()
        self._running = False
        self._worker = None

    def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        worker = _DailyBackupWorker(self.service)
        worker.signals.completed.connect(self._completed)
        worker.signals.failed.connect(self._failed)
        self._worker = worker
        self.pool.start(worker)
        return True

    def _set_status(self, text: str) -> None:
        notify = getattr(self.window, "_notify_known_state", None)
        if callable(notify):
            notify(text)
        else:
            self.window.setProperty("dailyBackupStatus", text)

    @Slot(object)
    def _completed(self, result) -> None:
        self._running = False
        self._worker = None
        status = getattr(result, "status", "FALHA")
        destinations = tuple(getattr(result, "destinations", ()))
        succeeded = sum(bool(item.succeeded) for item in destinations)
        total = len(destinations)
        if status == "DESATIVADO":
            self._set_status("Backup diário desativado")
            return
        if status == "JA_CONCLUIDO":
            self._set_status(f"Backup diário já concluído ({total}/{total} destinos)")
            return
        if status == "SUCESSO":
            self._set_status(f"Backup diário concluído ({succeeded}/{total} destinos)")
            return
        label = "parcial" if status == "PARCIAL" else "falhou"
        self._set_status(f"Backup diário {label} ({succeeded}/{total} destinos)")
        details = "\n".join(getattr(result, "errors", ())) or "Nenhuma cópia foi confirmada."
        QMessageBox.warning(
            self.window,
            "Proteção dos dados",
            f"O backup diário ficou {label}.\n\n{details}\n\n"
            "O backup contém dados pessoais e deve permanecer em destino protegido.",
        )

    @Slot(object)
    def _failed(self, error) -> None:
        self._running = False
        self._worker = None
        self._set_status("Backup diário falhou (0 destinos confirmados)")
        QMessageBox.warning(
            self.window,
            "Proteção dos dados",
            f"O backup diário falhou: {error}\n\n"
            "Nenhum destino foi marcado como concluído. O backup contém dados "
            "pessoais e deve permanecer em destino protegido.",
        )
