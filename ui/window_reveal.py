"""Montagem e revelação estável de janelas secundárias."""

from __future__ import annotations

from typing import Any
import tkinter as tk
import time


def prepare_hidden_toplevel(window: Any) -> None:
    """Mantém o Toplevel retirado enquanto seus widgets são construídos."""
    window.withdraw()


def reveal_prepared_toplevel(
    window: Any,
    *,
    maximize: bool = False,
    grab: bool = False,
    focus_widget: Any | None = None,
) -> None:
    """Revela uma janela somente depois de concluir layout e geometria."""
    window.update_idletasks()
    if maximize:
        try:
            window.state("zoomed")
        except tk.TclError:
            width = max(1024, int(window.winfo_screenwidth() * 0.94))
            height = max(650, int(window.winfo_screenheight() * 0.90))
            window.geometry(f"{width}x{height}+0+0")
    window.deiconify()
    window.lift()
    if grab:
        window.grab_set()
    window.focus_force()
    if focus_widget is not None:
        focus_widget.focus_set()


def reveal_prepared_toplevel_when_idle(
    window: Any,
    *,
    maximize: bool = False,
    grab: bool = False,
    focus_widget: Any | None = None,
) -> None:
    """Agenda a revelação para o fim do ciclo atual, sem atraso temporal."""
    window.after_idle(
        lambda: reveal_prepared_toplevel(
            window,
            maximize=maximize,
            grab=grab,
            focus_widget=focus_widget,
        )
    )


def reveal_prepared_toplevel_smooth(
    window: Any,
    *,
    grab: bool = False,
    focus_widget: Any | None = None,
    duration_ms: int = 320,
) -> None:
    """Revela um Toplevel pronto com fade curto, sem bloquear o event loop."""

    window.update_idletasks()
    duration = max(1, int(duration_ms)) / 1000.0
    started_at = time.monotonic()
    alpha_supported = True
    try:
        window.attributes("-alpha", 0.0)
    except (tk.TclError, TypeError):
        alpha_supported = False
    window.deiconify()
    window.lift()
    if grab:
        window.grab_set()

    def finish() -> None:
        try:
            if alpha_supported:
                window.attributes("-alpha", 1.0)
            window.lift()
            if focus_widget is not None:
                focus_widget.focus_set()
            else:
                window.focus_force()
        except tk.TclError:
            return

    if not alpha_supported:
        finish()
        return

    def step() -> None:
        try:
            progress = min(1.0, (time.monotonic() - started_at) / duration)
            eased = progress * progress * (3.0 - 2.0 * progress)
            window.attributes("-alpha", eased)
            if progress < 1.0:
                window.after(16, step)
            else:
                finish()
        except tk.TclError:
            return

    window.after(16, step)
