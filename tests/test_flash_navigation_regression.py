from __future__ import annotations

import ast
from pathlib import Path
import tkinter as tk

from ui.window_reveal import (
    prepare_hidden_toplevel,
    reveal_prepared_toplevel,
    reveal_prepared_toplevel_when_idle,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeWindow:
    def __init__(self) -> None:
        self.calls = []

    def withdraw(self): self.calls.append("withdraw")
    def update_idletasks(self): self.calls.append("update_idletasks")
    def state(self, value): self.calls.append(("state", value))
    def deiconify(self): self.calls.append("deiconify")
    def lift(self): self.calls.append("lift")
    def grab_set(self): self.calls.append("grab_set")
    def focus_force(self): self.calls.append("focus_force")
    def after_idle(self, callback): self.calls.append("after_idle"); self.callback = callback


class FakeFocus:
    def __init__(self, calls): self.calls = calls
    def focus_set(self): self.calls.append("focus_set")


class FakeFallbackWindow(FakeWindow):
    def state(self, value):
        super().state(value)
        raise tk.TclError("zoom unavailable")
    def winfo_screenwidth(self): return 1600
    def winfo_screenheight(self): return 900
    def geometry(self, value): self.calls.append(("geometry", value))


def _method_source(name: str) -> str:
    source = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")
    method = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, method) or ""


def test_hidden_toplevel_is_revealed_only_after_layout_and_maximize():
    window = FakeWindow()
    focus = FakeFocus(window.calls)
    prepare_hidden_toplevel(window)
    reveal_prepared_toplevel(window, maximize=True, focus_widget=focus)
    assert window.calls == [
        "withdraw", "update_idletasks", ("state", "zoomed"), "deiconify",
        "lift", "focus_force", "focus_set",
    ]


def test_zoom_fallback_is_computed_before_mapping():
    window = FakeFallbackWindow()
    reveal_prepared_toplevel(window, maximize=True)
    assert window.calls[:4] == [
        "update_idletasks", ("state", "zoomed"),
        ("geometry", "1504x810+0+0"), "deiconify",
    ]


def test_idle_reveal_has_no_timed_delay_or_immediate_mapping():
    window = FakeWindow()
    reveal_prepared_toplevel_when_idle(window, grab=True)
    assert window.calls == ["after_idle"]
    window.callback()
    assert window.calls[1:] == ["update_idletasks", "deiconify", "lift", "grab_set", "focus_force"]


def test_pdv_does_not_maximize_or_map_during_construction():
    source = _method_source("abrir_pdv_independente")
    construction = source.split("def revelar_pdv_pronto", 1)[0]
    assert "prepare_hidden_toplevel(win)" in construction
    assert 'win.state("zoomed")' not in construction
    assert "win.deiconify()" not in construction
    assert "reveal_prepared_toplevel_when_idle(" in source
    assert "maximize=True" in source
    assert 'attributes("-alpha"' not in source


def test_regular_navigation_prepares_before_raise_without_removal():
    source = _method_source("mostrar_tela")
    assert source.index("self._preparar_tela_para_exibicao(nome)") < source.index("self.telas[nome].tkraise()")
    for forbidden in ("destroy(", "pack_forget(", "grid_forget(", "grid_remove(", "place_forget("):
        assert forbidden not in source


def test_histories_follow_hidden_build_contract():
    notifications = _method_source("abrir_historico_notificacoes")
    clients = _method_source("abrir_historico_cliente")
    assert notifications.index("prepare_hidden_toplevel(janela)") < notifications.rindex("tabela.insert(")
    assert notifications.rindex("reveal_prepared_toplevel_when_idle(janela)") > notifications.rindex("tabela.insert(")
    assert clients.index("prepare_hidden_toplevel(win)") < clients.rindex("ctk.CTkButton(")
    assert clients.rindex("reveal_prepared_toplevel_when_idle(win, grab=True)") > clients.rindex("ctk.CTkButton(")
