"""Navegação inteligente por Enter para formulários Tk/CustomTkinter.

O fluxo é explícito por formulário: Enter avança, Shift+Enter retorna e o Enter
no último campo executa a ação principal. Campos ocultos, desabilitados ou sem
foco são ignorados. A validação pode bloquear o avanço e reposicionar o foco.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Sequence

from ui.keyboard_navigation import bind_enter_pair


ValidationCallback = Callable[[], bool]
ActionCallback = Callable[[], Any]


@dataclass
class EnterField:
    widget: Any
    validate: Optional[ValidationCallback] = None


class IntelligentEnterNavigator:
    """Gerencia uma sequência de campos com finalização inteligente."""

    def __init__(
        self,
        fields: Sequence[Any | EnterField],
        *,
        on_finish: ActionCallback,
        on_invalid: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        self.fields = [item if isinstance(item, EnterField) else EnterField(item) for item in fields]
        self.on_finish = on_finish
        self.on_invalid = on_invalid
        self._installed = False

    @staticmethod
    def _state(widget: Any) -> str:
        try:
            return str(widget.cget("state"))
        except Exception:
            try:
                return str(widget["state"])
            except Exception:
                return "normal"

    @classmethod
    def _is_available(cls, widget: Any) -> bool:
        if widget is None:
            return False
        if cls._state(widget).lower() in {"disabled", "readonly-disabled"}:
            return False
        try:
            if not bool(widget.winfo_exists()):
                return False
        except Exception:
            pass
        try:
            # winfo_viewable pode retornar 0 antes do primeiro redraw; nesse caso
            # o widget ainda é utilizável se estiver gerenciado pelo layout.
            if hasattr(widget, "winfo_manager") and not widget.winfo_manager():
                return False
        except Exception:
            pass
        return True

    def _available_indexes(self) -> list[int]:
        return [index for index, field in enumerate(self.fields) if self._is_available(field.widget)]

    def _index_of(self, widget: Any) -> Optional[int]:
        for index, field in enumerate(self.fields):
            if field.widget is widget:
                return index
        return None

    @staticmethod
    def _focus(widget: Any) -> None:
        try:
            widget.focus_set()
        except Exception:
            return
        for method_name in ("select_range", "selection_range"):
            try:
                getattr(widget, method_name)(0, "end")
                break
            except Exception:
                continue

    def _validate(self, index: int) -> bool:
        callback = self.fields[index].validate
        if callback is None:
            return True
        try:
            valid = bool(callback())
        except Exception:
            valid = False
        if not valid:
            widget = self.fields[index].widget
            self._focus(widget)
            if self.on_invalid is not None:
                self.on_invalid(widget)
        return valid

    def advance(self, widget: Any) -> str:
        index = self._index_of(widget)
        if index is None:
            return "break"
        if not self._validate(index):
            return "break"

        available = self._available_indexes()
        if index not in available:
            return "break"
        position = available.index(index)
        if position < len(available) - 1:
            self._focus(self.fields[available[position + 1]].widget)
            return "break"

        self.on_finish()
        return "break"

    def previous(self, widget: Any) -> str:
        index = self._index_of(widget)
        if index is None:
            return "break"
        available = self._available_indexes()
        if index not in available:
            return "break"
        position = available.index(index)
        if position > 0:
            self._focus(self.fields[available[position - 1]].widget)
        return "break"

    def install(self) -> "IntelligentEnterNavigator":
        if self._installed:
            return self
        for field in self.fields:
            widget = field.widget
            owner = f"enter-navigation:{id(self)}:{id(widget)}"
            try:
                bind_enter_pair(
                    widget,
                    lambda event, w=widget: self.advance(w),
                    owner=owner,
                )
                bind_enter_pair(
                    widget,
                    lambda event, w=widget: self.previous(w),
                    owner=f"{owner}:previous",
                    shift=True,
                )
            except Exception:
                continue
        self._installed = True
        return self


def install_enter_navigation(
    fields: Iterable[Any | EnterField],
    *,
    on_finish: ActionCallback,
    on_invalid: Optional[Callable[[Any], Any]] = None,
) -> IntelligentEnterNavigator:
    return IntelligentEnterNavigator(
        list(fields), on_finish=on_finish, on_invalid=on_invalid
    ).install()
