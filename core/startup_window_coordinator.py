"""Coordenação segura entre a splash e os modais do startup.

A splash roda em outro processo. Este módulo usa apenas um arquivo-sinal para
pedir que ela se oculte enquanto uma janela obrigatória do NabiCode aguarda o
usuário. Nenhum loop de interface ou objeto Tk atravessa processos/threads.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Iterator


SPLASH_PAUSE_ENV = "NABICODE_SPLASH_PAUSE_FILE"
_state_lock = RLock()
_modal_depth = 0


def splash_pause_path() -> Path | None:
    value = os.environ.get(SPLASH_PAUSE_ENV, "").strip()
    return Path(value) if value else None


def _set_splash_paused(paused: bool) -> None:
    path = splash_pause_path()
    if path is None:
        return
    try:
        if paused:
            path.touch(exist_ok=True)
        else:
            path.unlink(missing_ok=True)
    except OSError:
        # O modal não pode falhar apenas porque o processo da splash encerrou.
        return


@contextmanager
def startup_modal_scope() -> Iterator[None]:
    """Oculta a splash durante um modal obrigatório, com suporte a aninhamento."""

    global _modal_depth
    with _state_lock:
        _modal_depth += 1
        if _modal_depth == 1:
            _set_splash_paused(True)
    try:
        yield
    finally:
        with _state_lock:
            _modal_depth = max(0, _modal_depth - 1)
            if _modal_depth == 0:
                _set_splash_paused(False)


def prepare_startup_modal(window, parent) -> None:
    """Aplica propriedade, modalidade e foco sem manter topmost permanente."""

    if parent is not None:
        window.transient(parent)
    window.grab_set()
    window.lift()
    try:
        window.focus_force()
    except Exception:
        window.focus_set()


def reset_startup_modal_state_for_tests() -> None:
    """Restaura o estado global; uso restrito a isolamento de testes."""

    global _modal_depth
    with _state_lock:
        _modal_depth = 0
        _set_splash_paused(False)
