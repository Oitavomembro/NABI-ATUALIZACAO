from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .windows_shell_dispatcher import WindowsShellDispatcher


class WindowsPDFPrintError(RuntimeError):
    """Raised when Windows cannot dispatch a PDF to the associated reader."""


class WindowsPDFPrinter(WindowsShellDispatcher):
    """Dispatches PDF printing through an isolated PowerShell process.

    This avoids ``os.startfile(path, 'print')``, which can crash CPython 3.14
    with some PDF shell extensions because the callback returns with an
    invalid thread state.
    """

    default_runner = subprocess.run

    def command(self, pdf_path: str | os.PathLike[str], printer: str) -> list[str]:
        path = str(Path(pdf_path).resolve())
        if printer == "Padrão do Sistema":
            script = f"Start-Process -FilePath {self._ps_quote(path)} -Verb Print"
        else:
            script = (
                f"Start-Process -FilePath {self._ps_quote(path)} -Verb PrintTo "
                f"-ArgumentList @({self._ps_quote(printer)})"
            )
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]

    def print(self, pdf_path: str | os.PathLike[str], printer: str) -> str:
        path = Path(pdf_path).resolve()
        if not self._is_windows:
            raise WindowsPDFPrintError(
                "A impressão automática de PDF está disponível apenas no Windows."
            )
        if not path.is_file():
            raise FileNotFoundError(f"O PDF não foi encontrado:\n{path}")
        try:
            self._runner(
                self.command(path, printer),
                check=True,
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as exc:
            raise WindowsPDFPrintError(
                "O Windows não aceitou a impressão automática do PDF."
            ) from exc
        return printer
