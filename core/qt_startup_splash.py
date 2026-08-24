from __future__ import annotations


class QtStartupSplash:
    """Reutiliza o splash canônico do Legacy no ponto de entrada Qt."""

    def __init__(self) -> None:
        from main import _start_splash
        self.process, self.stop_file, self.pause_file, self.metadata_file, self.error_file = _start_splash()
        self.closed = False

    def close(self) -> None:
        if self.closed: return
        self.closed = True
        from main import _cleanup_splash_files, _ensure_process_stopped, _stop_splash
        _stop_splash(self.stop_file)
        _ensure_process_stopped(self.process, timeout=15.0)
        _cleanup_splash_files(self.stop_file, self.pause_file, self.metadata_file, self.error_file)

    def __enter__(self): return self

    def __exit__(self, *_args): self.close()
