from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .windows_shell_dispatcher import WindowsShellDispatcher


class WindowsFileOpenError(RuntimeError):
    """Raised when Windows cannot open a file with its associated application."""


class WindowsFileOpener(WindowsShellDispatcher):
    """Opens a file through an isolated PowerShell process.

    Calling ``os.startfile`` inside CPython 3.14 can crash the interpreter when
    a Windows shell extension returns with an invalid thread state. Dispatching
    the shell action from another process keeps the NabiCode process isolated.
    """

    default_runner = subprocess.Popen

    def command(self, file_path: str | os.PathLike[str]) -> list[str]:
        path = str(Path(file_path).resolve())
        script = f"Start-Process -FilePath {self._ps_quote(path)}"
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]

    def open(self, file_path: str | os.PathLike[str]) -> str:
        path = Path(file_path).resolve()
        if not self._is_windows:
            raise WindowsFileOpenError(
                "A abertura isolada de arquivos está disponível apenas no Windows."
            )
        if not path.is_file():
            raise FileNotFoundError(f"O arquivo não foi encontrado:\n{path}")
        try:
            self._runner(
                self.command(path),
                # O PowerShell é o processo isolador; não o destacamos do
                # console com DETACHED_PROCESS porque isso pode impedir o
                # ShellExecute/Start-Process de herdar um desktop interativo
                # válido em algumas instalações do Windows.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception as exc:
            raise WindowsFileOpenError(
                "O Windows não conseguiu abrir o arquivo no aplicativo associado."
            ) from exc
        return str(path)

    def open_directory(self, directory_path: str | os.PathLike[str]) -> str:
        path = Path(directory_path).resolve()
        if not self._is_windows:
            raise WindowsFileOpenError(
                "A abertura isolada de pastas está disponível apenas no Windows."
            )
        if not path.is_dir():
            raise FileNotFoundError(f"A pasta não foi encontrada:\n{path}")
        try:
            self._runner(
                self.command(path),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception as exc:
            raise WindowsFileOpenError(
                "O Windows não conseguiu abrir a pasta."
            ) from exc
        return str(path)
