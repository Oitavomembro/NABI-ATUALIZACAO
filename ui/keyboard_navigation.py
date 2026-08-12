"""Primitivas visuais para bindings de teclado sem duplicação.

Não contém regra de negócio. O objetivo é garantir que Enter e KP_Enter usem
sempre o mesmo callback e que uma mesma responsabilidade não seja instalada
mais de uma vez no mesmo widget.
"""
from __future__ import annotations

from typing import Any, Callable


_ENTER_BINDINGS_ATTR = "_nabicode_enter_bindings"


def _registry(widget: Any) -> set[str]:
    registry = getattr(widget, _ENTER_BINDINGS_ATTR, None)
    if registry is None:
        registry = set()
        try:
            setattr(widget, _ENTER_BINDINGS_ATTR, registry)
        except Exception:
            # Widgets exóticos podem bloquear atributos arbitrários. Nesses
            # casos, ainda instalamos o binding; apenas a deduplicação local
            # deixa de ser possível.
            return set()
    return registry


def bind_key_once(
    widget: Any,
    sequence: str,
    callback: Callable[[Any], Any],
    *,
    owner: str,
    add: str = "+",
) -> bool:
    """Instala um binding uma única vez por ``owner``/sequência/widget."""
    token = f"{owner}:{sequence}"
    registry = _registry(widget)
    if token in registry:
        return False
    widget.bind(sequence, callback, add=add)
    registry.add(token)
    return True


def bind_enter_pair(
    widget: Any,
    callback: Callable[[Any], Any],
    *,
    owner: str,
    shift: bool = False,
    add: str = "+",
) -> None:
    """Mantém Return e KP_Enter semanticamente idênticos."""
    sequences = (
        ("<Shift-Return>", "<Shift-KP_Enter>")
        if shift
        else ("<Return>", "<KP_Enter>")
    )
    for sequence in sequences:
        bind_key_once(widget, sequence, callback, owner=owner, add=add)


_ARROW_NAV_ATTR = "_nabicode_global_arrow_navigation"


def _ancestor_type_names(widget: Any) -> set[str]:
    names: set[str] = set()
    current = widget
    seen: set[int] = set()
    while current is not None:
        marker = id(current)
        if marker in seen:
            break
        seen.add(marker)
        names.add(type(current).__name__)
        current = getattr(current, "master", None)
    return names


def _preserve_native_arrow_behavior(widget: Any) -> bool:
    """Não rouba setas de campos/listas que já usam as teclas semanticamente."""
    names = _ancestor_type_names(widget)
    native_names = {
        "Entry", "Text", "Listbox", "Treeview", "Combobox", "Spinbox", "Scale",
        "CTkEntry", "CTkTextbox", "CTkComboBox", "CTkSlider", "CTkScrollableFrame",
    }
    if names & native_names:
        return True
    try:
        widget_class = str(widget.winfo_class())
    except Exception:
        widget_class = ""
    return widget_class in {"Entry", "Text", "TEntry", "Treeview", "TCombobox", "Listbox", "Spinbox", "Scale"}


def _move_focus(widget: Any, *, forward: bool) -> str | None:
    if widget is None or _preserve_native_arrow_behavior(widget):
        return None
    try:
        target = widget.tk_focusNext() if forward else widget.tk_focusPrev()
    except Exception:
        return None
    if target in (None, widget):
        return None
    try:
        target.focus_set()
    except Exception:
        return None
    return "break"


def install_global_arrow_navigation(root: Any) -> None:
    """Usa setas para navegar opções/botões sem interferir em edição e tabelas.

    Direita/Baixo avançam; Esquerda/Cima retornam. Entradas, Treeviews,
    Comboboxes, sliders e listas preservam o comportamento nativo das setas.
    """
    if getattr(root, _ARROW_NAV_ATTR, False):
        return
    setattr(root, _ARROW_NAV_ATTR, True)

    def handler(event: Any, *, forward: bool) -> str | None:
        state = int(getattr(event, "state", 0) or 0)
        # Ctrl/Alt/Meta continuam disponíveis para atalhos do sistema/aplicação.
        if state & 0x0004 or state & 0x0008 or state & 0x0080:
            return None
        return _move_focus(getattr(event, "widget", None), forward=forward)

    for sequence in ("<Right>", "<Down>"):
        root.bind_all(sequence, lambda event, f=True: handler(event, forward=f), add="+")
    for sequence in ("<Left>", "<Up>"):
        root.bind_all(sequence, lambda event, f=False: handler(event, forward=f), add="+")
