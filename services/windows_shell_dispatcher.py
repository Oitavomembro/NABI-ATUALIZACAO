from __future__ import annotations

import os
from typing import Callable


class WindowsShellDispatcher:
    """Estado comum para adaptadores isolados do shell do Windows."""

    default_runner: Callable[..., object]

    def __init__(
        self,
        *,
        runner: Callable[..., object] | None = None,
        is_windows: bool | None = None,
    ) -> None:
        self._runner = self.default_runner if runner is None else runner
        self._is_windows = (os.name == "nt") if is_windows is None else bool(is_windows)

    @staticmethod
    def _ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"
