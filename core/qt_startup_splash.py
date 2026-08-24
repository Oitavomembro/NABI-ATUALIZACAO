from __future__ import annotations

import logging
import os


class QtStartupSplash:
    """Reutiliza o splash canônico do Legacy no ponto de entrada Qt."""

    def __init__(self) -> None:
        self.closed = False
        self.process = None
        self.stop_file = self.pause_file = self.metadata_file = self.error_file = None
        try:
            from main import _start_splash
            (
                self.process, self.stop_file, self.pause_file,
                self.metadata_file, self.error_file,
            ) = _start_splash()
        except Exception:
            logging.getLogger("NabiCode.Qt").exception(
                "Splash indisponível; o Qt continuará sem animação."
            )
            self._clear_pause_environment()

    def close(self) -> None:
        if self.closed: return
        self.closed = True
        try:
            if self.stop_file is not None:
                from main import _cleanup_splash_files, _ensure_process_stopped, _stop_splash
                _stop_splash(self.stop_file)
                _ensure_process_stopped(self.process, timeout=15.0)
                _cleanup_splash_files(*(
                    path for path in (
                        self.stop_file, self.pause_file, self.metadata_file,
                        self.error_file,
                    ) if path is not None
                ))
        except Exception:
            logging.getLogger("NabiCode.Qt").exception(
                "Falha recuperável ao encerrar o splash Qt."
            )
        finally:
            self._clear_pause_environment()

    def _clear_pause_environment(self):
        from core.startup_window_coordinator import SPLASH_PAUSE_ENV
        current = os.environ.get(SPLASH_PAUSE_ENV)
        if self.pause_file is None or current == str(self.pause_file):
            os.environ.pop(SPLASH_PAUSE_ENV, None)

    def __enter__(self): return self

    def __exit__(self, *_args): self.close()
