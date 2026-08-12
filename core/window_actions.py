"""Ações universais de janela do NabiCode.

Centraliza Ctrl+S, Del e Esc com confirmação consistente, sem obrigar cada
formulário a repetir bindings e regras de segurança.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox
import weakref


Action = Callable[[], Any]
Predicate = Callable[[], bool]
Description = Callable[[], str]


@dataclass
class WindowActionRegistration:
    save: Optional[Action] = None
    delete: Optional[Action] = None
    close: Optional[Action] = None
    is_dirty: Optional[Predicate] = None
    delete_description: Optional[Description] = None
    confirm_delete: bool = True
    confirm_close: bool = True
    title: str = "NabiCode"


class WindowActionController:
    """Registra e executa ações padronizadas em toplevels Tk/CustomTkinter."""

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._registrations: "weakref.WeakKeyDictionary[tk.Misc, WindowActionRegistration]" = weakref.WeakKeyDictionary()

    def register(
        self,
        window: tk.Misc,
        *,
        save: Optional[Action] = None,
        delete: Optional[Action] = None,
        close: Optional[Action] = None,
        is_dirty: Optional[Predicate] = None,
        delete_description: Optional[Description] = None,
        confirm_delete: bool = True,
        confirm_close: bool = True,
        title: str = "NabiCode",
    ) -> WindowActionRegistration:
        registration = WindowActionRegistration(
            save=save,
            delete=delete,
            close=close,
            is_dirty=is_dirty,
            delete_description=delete_description,
            confirm_delete=confirm_delete,
            confirm_close=confirm_close,
            title=title,
        )
        self._registrations[window] = registration
        window.bind("<<NabiSave>>", lambda _event: self.save(window), add="+")
        window.bind("<<NabiDelete>>", lambda _event: self.delete(window), add="+")
        window.bind("<<NabiClose>>", lambda _event: self.close(window), add="+")
        try:
            window.protocol("WM_DELETE_WINDOW", lambda: self.close(window))
        except Exception:
            pass
        return registration

    def unregister(self, window: tk.Misc) -> None:
        self._registrations.pop(window, None)

    def registration_for(self, window: tk.Misc) -> Optional[WindowActionRegistration]:
        return self._registrations.get(window)

    @staticmethod
    def _action_succeeded(result: Any) -> bool:
        return result is not False

    def save(self, window: tk.Misc) -> str:
        registration = self.registration_for(window)
        if registration is None or registration.save is None:
            try:
                window.bell()
            except Exception:
                pass
            return "break"
        try:
            registration.save()
        except Exception as exc:
            messagebox.showerror(registration.title, f"Não foi possível salvar.\n\n{exc}", parent=window)
        return "break"

    def delete(self, window: tk.Misc) -> str:
        registration = self.registration_for(window)
        if registration is None or registration.delete is None:
            try:
                window.bell()
            except Exception:
                pass
            return "break"
        descricao = "o item selecionado"
        if registration.delete_description is not None:
            try:
                descricao = registration.delete_description() or descricao
            except Exception:
                pass
        if registration.confirm_delete:
            confirmado = messagebox.askyesno(
                "Confirmar exclusão",
                f"Deseja realmente excluir {descricao}?\n\nEsta ação pode não ser reversível.",
                parent=window,
            )
            if not confirmado:
                return "break"
        try:
            registration.delete()
        except Exception as exc:
            messagebox.showerror(registration.title, f"Não foi possível excluir.\n\n{exc}", parent=window)
        return "break"

    def close(self, window: tk.Misc) -> str:
        registration = self.registration_for(window)
        if registration is None:
            try:
                window.destroy()
            except Exception:
                pass
            return "break"

        dirty = False
        if registration.is_dirty is not None:
            try:
                dirty = bool(registration.is_dirty())
            except Exception:
                dirty = True

        if registration.confirm_close and dirty:
            resposta = messagebox.askyesnocancel(
                "Alterações não salvas",
                "Existem alterações não salvas.\n\nDeseja salvar antes de fechar?",
                parent=window,
            )
            if resposta is None:
                return "break"
            if resposta:
                if registration.save is None:
                    return "break"
                try:
                    resultado = registration.save()
                except Exception as exc:
                    messagebox.showerror(registration.title, f"Não foi possível salvar.\n\n{exc}", parent=window)
                    return "break"
                if not self._action_succeeded(resultado):
                    return "break"
                # A rotina de salvar pode destruir a janela.
                try:
                    if not window.winfo_exists():
                        return "break"
                except Exception:
                    return "break"

        try:
            if registration.close is not None:
                registration.close()
            else:
                window.destroy()
        finally:
            self.unregister(window)
        return "break"
