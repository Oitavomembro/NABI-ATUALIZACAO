from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Callable

import customtkinter as ctk


MONTH_NAMES = (
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


def open_date_picker(parent, *, initial: str, on_select: Callable[[str], None], title: str = "Selecionar data"):
    """Calendário mensal nativo, sem dependência externa e com retorno ISO."""
    try:
        selected = datetime.strptime(str(initial)[:10], "%Y-%m-%d").date()
    except ValueError:
        selected = date.today()
    state = {"year": selected.year, "month": selected.month}
    window = ctk.CTkToplevel(parent)
    window.title(title)
    window.geometry("390x430")
    window.resizable(False, False)
    window.transient(parent)
    header = ctk.CTkFrame(window, fg_color="transparent")
    header.pack(fill="x", padx=14, pady=(14, 8))
    grid = ctk.CTkFrame(window, fg_color="transparent")
    grid.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    month_label = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=16, weight="bold"))
    month_label.pack(side="left", fill="x", expand=True)

    def render():
        for child in grid.winfo_children():
            child.destroy()
        month_label.configure(text=f"{MONTH_NAMES[state['month']]} {state['year']}")
        for column, label in enumerate(("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")):
            ctk.CTkLabel(grid, text=label, text_color="#8b949e", width=44).grid(row=0, column=column, padx=2, pady=3)
        for row_index, week in enumerate(calendar.monthcalendar(state["year"], state["month"]), start=1):
            for column, day in enumerate(week):
                if not day:
                    continue
                chosen = date(state["year"], state["month"], day)
                ctk.CTkButton(
                    grid, text=str(day), width=44, height=38,
                    fg_color="#1f6feb" if chosen == selected else "#30363d",
                    command=lambda value=chosen: (on_select(value.isoformat()), window.destroy()),
                ).grid(row=row_index, column=column, padx=2, pady=3)

    def move(delta: int):
        month = state["month"] + delta
        state["year"] += (month - 1) // 12
        state["month"] = (month - 1) % 12 + 1
        render()

    ctk.CTkButton(header, text="‹", width=42, command=lambda: move(-1)).pack(side="left")
    ctk.CTkButton(header, text="›", width=42, command=lambda: move(1)).pack(side="right")
    render()
    window.grab_set()
    return window
