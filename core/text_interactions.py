"""Interações universais de edição, área de transferência e menu de contexto.

O módulo trabalha apenas com APIs públicas do Tk/Ttk. Widgets CustomTkinter
encapsulam Entry/Text nativos; o gerenciador percorre a hierarquia até localizar
um widget compatível, sem depender de atributos internos da biblioteca.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import tkinter as tk
from typing import Any, Optional


@dataclass(frozen=True)
class ClipboardResult:
    action: str
    changed: bool
    value: str = ""


def normalize_decimal_text(value: str) -> str:
    """Normaliza moeda/percentual brasileiro sem destruir sinal ou decimais.

    Exemplos:
        ``R$ 1.234,56`` -> ``1234.56``
        ``- 35,5 %``   -> ``-35.5``
        ``12.50``      -> ``12.50``
    """
    text = str(value or "").strip()
    if not text:
        return ""
    negative = "-" in text
    text = re.sub(r"[^0-9.,]", "", text)
    if not text:
        return "-" if negative else ""
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    if negative and text != "0":
        text = "-" + text.lstrip("-")
    return text


class UniversalTextInteractionManager:
    """Instala menu de contexto e atalhos de edição para toda a aplicação."""

    ENTRY_CLASSES = {"Entry", "TEntry", "Spinbox", "TSpinbox"}
    TEXT_CLASSES = {"Text"}
    TREE_CLASSES = {"Treeview"}

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._installed = False
        self._menu: Optional[tk.Menu] = None
        self._target: Optional[tk.Misc] = None

    @staticmethod
    def _class_name(widget: Any) -> str:
        try:
            return str(widget.winfo_class())
        except Exception:
            return ""

    @classmethod
    def _is_entry(cls, widget: Any) -> bool:
        return cls._class_name(widget) in cls.ENTRY_CLASSES

    @classmethod
    def _is_text(cls, widget: Any) -> bool:
        return cls._class_name(widget) in cls.TEXT_CLASSES

    @classmethod
    def _is_tree(cls, widget: Any) -> bool:
        return cls._class_name(widget) in cls.TREE_CLASSES

    @classmethod
    def _supported(cls, widget: Any) -> bool:
        return cls._is_entry(widget) or cls._is_text(widget) or cls._is_tree(widget)

    @classmethod
    def _resolve_widget(cls, widget: Any) -> Optional[tk.Misc]:
        current = widget
        for _ in range(5):
            if current is None:
                return None
            if cls._supported(current):
                return current
            current = getattr(current, "master", None)
        return None

    @staticmethod
    def _selection_exists(widget: tk.Misc) -> bool:
        try:
            if UniversalTextInteractionManager._is_entry(widget):
                return bool(widget.selection_present())
            if UniversalTextInteractionManager._is_text(widget):
                widget.index("sel.first")
                widget.index("sel.last")
                return True
            if UniversalTextInteractionManager._is_tree(widget):
                return bool(widget.selection())
        except Exception:
            return False
        return False

    @staticmethod
    def _is_readonly(widget: tk.Misc) -> bool:
        try:
            state = str(widget.cget("state"))
            return state in {"disabled", "readonly"}
        except Exception:
            return False

    def _clipboard_get(self) -> str:
        try:
            return str(self.root.clipboard_get())
        except Exception:
            return ""

    def _clipboard_set(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()

    def _selected_text(self, widget: tk.Misc) -> str:
        try:
            if self._is_entry(widget):
                return str(widget.selection_get())
            if self._is_text(widget):
                return str(widget.get("sel.first", "sel.last"))
            if self._is_tree(widget):
                rows = []
                for item_id in widget.selection():
                    item = widget.item(item_id)
                    values = [str(v) for v in item.get("values", ())]
                    text = str(item.get("text", ""))
                    if text:
                        values.insert(0, text)
                    rows.append("\t".join(values))
                return "\n".join(rows)
        except Exception:
            return ""
        return ""

    def copy(self, widget: Optional[tk.Misc] = None) -> ClipboardResult:
        target = widget or self._target
        if target is None:
            return ClipboardResult("copy", False)
        value = self._selected_text(target)
        if not value:
            return ClipboardResult("copy", False)
        self._clipboard_set(value)
        return ClipboardResult("copy", True, value)

    def cut(self, widget: Optional[tk.Misc] = None) -> ClipboardResult:
        target = widget or self._target
        if target is None or self._is_tree(target) or self._is_readonly(target):
            return ClipboardResult("cut", False)
        copied = self.copy(target)
        if not copied.changed:
            return ClipboardResult("cut", False)
        self.delete_selection(target)
        return ClipboardResult("cut", True, copied.value)

    def delete_selection(self, widget: Optional[tk.Misc] = None) -> ClipboardResult:
        target = widget or self._target
        if target is None or self._is_tree(target) or self._is_readonly(target):
            return ClipboardResult("delete", False)
        try:
            if self._is_entry(target) and target.selection_present():
                target.delete("sel.first", "sel.last")
                target.event_generate("<<NabiChanged>>", when="tail")
                return ClipboardResult("delete", True)
            if self._is_text(target):
                target.delete("sel.first", "sel.last")
                target.event_generate("<<NabiChanged>>", when="tail")
                return ClipboardResult("delete", True)
        except Exception:
            pass
        return ClipboardResult("delete", False)

    def paste(self, widget: Optional[tk.Misc] = None) -> ClipboardResult:
        target = widget or self._target
        if target is None or self._is_tree(target) or self._is_readonly(target):
            return ClipboardResult("paste", False)
        value = self._clipboard_get()
        if getattr(target, "nabicode_numeric", False):
            value = normalize_decimal_text(value)
        try:
            if self._is_entry(target):
                if target.selection_present():
                    target.delete("sel.first", "sel.last")
                target.insert("insert", value)
            elif self._is_text(target):
                try:
                    target.delete("sel.first", "sel.last")
                except Exception:
                    pass
                target.insert("insert", value)
            else:
                return ClipboardResult("paste", False)
            target.event_generate("<<NabiPaste>>", when="tail")
            target.event_generate("<<NabiChanged>>", when="tail")
            return ClipboardResult("paste", True, value)
        except Exception:
            return ClipboardResult("paste", False)

    def select_all(self, widget: Optional[tk.Misc] = None) -> ClipboardResult:
        target = widget or self._target
        if target is None:
            return ClipboardResult("select_all", False)
        try:
            if self._is_entry(target):
                target.select_range(0, "end")
                target.icursor("end")
            elif self._is_text(target):
                target.tag_add("sel", "1.0", "end-1c")
                target.mark_set("insert", "end-1c")
            elif self._is_tree(target):
                target.selection_set(target.get_children(""))
            else:
                return ClipboardResult("select_all", False)
            return ClipboardResult("select_all", True)
        except Exception:
            return ClipboardResult("select_all", False)

    @staticmethod
    def _generate_edit_event(widget: Optional[tk.Misc], event_name: str) -> ClipboardResult:
        if widget is None:
            return ClipboardResult(event_name, False)
        try:
            widget.event_generate(event_name)
            return ClipboardResult(event_name, True)
        except Exception:
            return ClipboardResult(event_name, False)

    def undo(self, widget: Optional[tk.Misc] = None) -> ClipboardResult:
        return self._generate_edit_event(widget or self._target, "<<Undo>>")

    def redo(self, widget: Optional[tk.Misc] = None) -> ClipboardResult:
        return self._generate_edit_event(widget or self._target, "<<Redo>>")

    def _build_menu(self, target: tk.Misc) -> tk.Menu:
        menu = tk.Menu(target, tearoff=False)
        readonly = self._is_readonly(target)
        tree = self._is_tree(target)
        selected = self._selection_exists(target)
        clipboard = bool(self._clipboard_get())

        if not tree:
            menu.add_command(label="Desfazer", command=lambda: self.undo(target))
            menu.add_command(label="Refazer", command=lambda: self.redo(target))
            menu.add_separator()
            menu.add_command(label="Recortar", command=lambda: self.cut(target), state="normal" if selected and not readonly else "disabled")
        menu.add_command(label="Copiar", command=lambda: self.copy(target), state="normal" if selected else "disabled")
        if not tree:
            menu.add_command(label="Colar", command=lambda: self.paste(target), state="normal" if clipboard and not readonly else "disabled")
            menu.add_command(label="Excluir", command=lambda: self.delete_selection(target), state="normal" if selected and not readonly else "disabled")
        menu.add_separator()
        menu.add_command(label="Selecionar tudo", command=lambda: self.select_all(target))
        return menu

    def _show_context_menu(self, event: Any) -> Optional[str]:
        target = self._resolve_widget(getattr(event, "widget", None))
        if target is None:
            return None
        self._target = target
        try:
            target.focus_set()
            if self._is_entry(target):
                target.icursor(f"@{event.x}")
            elif self._is_text(target):
                target.mark_set("insert", f"@{event.x},{event.y}")
        except Exception:
            pass
        try:
            if self._menu is not None:
                self._menu.destroy()
        except Exception:
            pass
        self._menu = self._build_menu(target)
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._menu.grab_release()
            except Exception:
                pass
        return "break"

    def _keyboard_action(self, action: str):
        def callback(event: Any) -> Optional[str]:
            target = self._resolve_widget(getattr(event, "widget", None))
            if target is None:
                return None
            result = getattr(self, action)(target)
            return "break" if result.changed else None
        return callback

    def install(self) -> None:
        if self._installed:
            return
        for sequence in ("<Button-3>", "<Shift-F10>"):
            self.root.bind_all(sequence, self._show_context_menu, add="+")
        bindings = {
            "<Control-c>": "copy",
            "<Control-C>": "copy",
            "<Control-x>": "cut",
            "<Control-X>": "cut",
            "<Control-v>": "paste",
            "<Control-V>": "paste",
            "<Control-a>": "select_all",
            "<Control-A>": "select_all",
            "<Control-z>": "undo",
            "<Control-Z>": "undo",
            "<Control-y>": "redo",
            "<Control-Y>": "redo",
        }
        # Substitui apenas os atalhos de edição das classes suportadas. Usar
        # bind_all aqui faria o binding nativo executar antes e colaria duas vezes.
        editable_classes = tuple(sorted(self.ENTRY_CLASSES | self.TEXT_CLASSES))
        for sequence, action in bindings.items():
            callback = self._keyboard_action(action)
            target_classes = editable_classes
            if action in {"copy", "select_all"}:
                target_classes = editable_classes + tuple(sorted(self.TREE_CLASSES))
            for class_name in target_classes:
                try:
                    self.root.bind_class(class_name, sequence, callback)
                except Exception:
                    # Ambientes de teste podem fornecer um root mínimo.
                    self.root.bind_all(sequence, callback, add="+")
        self._installed = True

    @property
    def installed(self) -> bool:
        return self._installed
