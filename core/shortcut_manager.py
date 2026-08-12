"""Atalhos globais e consistentes do NabiCode.

O gerenciador concentra bindings comuns sem obrigar cada tela a repetir código.
Ações de negócio são publicadas como eventos virtuais Tk, permitindo que cada
janela trate somente o que realmente suporta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
import tkinter as tk


@dataclass(frozen=True)
class ShortcutDefinition:
    sequence: str
    virtual_event: str
    description: str


GLOBAL_SHORTCUTS = (
    ShortcutDefinition("<Control-s>", "<<NabiSave>>", "Salvar"),
    ShortcutDefinition("<Control-n>", "<<NabiNew>>", "Novo"),
    ShortcutDefinition("<Control-e>", "<<NabiEdit>>", "Editar"),
    ShortcutDefinition("<Control-f>", "<<NabiSearch>>", "Pesquisar"),
    ShortcutDefinition("<Control-p>", "<<NabiPrint>>", "Imprimir"),
    ShortcutDefinition("<Control-k>", "<<NabiCommandPalette>>", "Pesquisa global"),
    ShortcutDefinition("<F1>", "<<NabiHelp>>", "Ajuda"),
)


class GlobalShortcutManager:
    """Instala e despacha atalhos globais respeitando o widget em foco."""

    TEXT_CLASSES = {"Entry", "TEntry", "Text", "Spinbox", "TSpinbox"}

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._installed = False
        self._bindings: Dict[str, str] = {}

    @staticmethod
    def _is_text_input(widget: Any) -> bool:
        try:
            return widget.winfo_class() in GlobalShortcutManager.TEXT_CLASSES
        except Exception:
            return False

    def _active_toplevel(self) -> tk.Misc:
        try:
            focused = self.root.focus_get()
            if focused is not None:
                return focused.winfo_toplevel()
        except Exception:
            pass
        return self.root

    @staticmethod
    def _emit(target: tk.Misc, virtual_event: str) -> str:
        try:
            target.event_generate(virtual_event, when="tail")
        except Exception:
            return "break"
        return "break"

    def _dispatch_virtual(self, virtual_event: str) -> Callable[[Any], str]:
        def callback(event: Any) -> str:
            target = self._active_toplevel()
            return self._emit(target, virtual_event)
        return callback

    def _delete(self, event: Any) -> Optional[str]:
        # Delete deve manter seu comportamento normal dentro de campos de texto.
        if self._is_text_input(getattr(event, "widget", None)):
            return None
        return self._emit(self._active_toplevel(), "<<NabiDelete>>")

    def _escape(self, _event: Any) -> str:
        return self._emit(self._active_toplevel(), "<<NabiClose>>")

    def _minimize(self, _event: Any) -> str:
        target = self._active_toplevel()
        try:
            target.iconify()
        except Exception:
            pass
        return "break"

    def _fullscreen(self, _event: Any) -> str:
        target = self._active_toplevel()
        try:
            atual = bool(target.attributes("-fullscreen"))
            target.attributes("-fullscreen", not atual)
        except Exception:
            pass
        return "break"

    def install(self) -> None:
        if self._installed:
            return

        for definition in GLOBAL_SHORTCUTS:
            binding_id = self.root.bind_all(
                definition.sequence,
                self._dispatch_virtual(definition.virtual_event),
                add="+",
            )
            self._bindings[definition.sequence] = binding_id or ""

        special = {
            "<Delete>": self._delete,
            "<Escape>": self._escape,
            "<Control-m>": self._minimize,
            "<F11>": self._fullscreen,
        }
        for sequence, callback in special.items():
            binding_id = self.root.bind_all(sequence, callback, add="+")
            self._bindings[sequence] = binding_id or ""

        self._installed = True

    @property
    def installed(self) -> bool:
        return self._installed
