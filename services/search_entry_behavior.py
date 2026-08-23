from __future__ import annotations

from typing import Any, Callable, Optional

from ui.keyboard_navigation import bind_enter_pair, bind_key_once


class SearchEntryBehavior:
    """Comportamento reutilizável para campos de pesquisa Tk/CustomTkinter.

    A configuração visual é aplicada conforme as opções realmente suportadas
    pelo widget. Um ``tk.Entry`` nunca recebe opções exclusivas de CTkEntry.
    """

    TEXT_COLOR = "#ffffff"
    PLACEHOLDER_COLOR = "#8b949e"

    @classmethod
    def configure(cls, entry: Any) -> None:
        # CustomTkinter: suporta text_color e placeholder_text_color.
        try:
            entry.configure(
                text_color=cls.TEXT_COLOR,
                placeholder_text_color=cls.PLACEHOLDER_COLOR,
            )
            return
        except Exception:
            pass

        # Tk clássico: usa fg/insertbackground e não possui placeholder nativo.
        try:
            entry.configure(fg=cls.TEXT_COLOR, insertbackground=cls.TEXT_COLOR)
            return
        except Exception:
            pass

        # ttk.Entry e implementações compatíveis podem aceitar foreground.
        try:
            entry.configure(foreground=cls.TEXT_COLOR)
        except Exception:
            # A aparência não pode interromper pesquisa, foco ou navegação.
            return

    @classmethod
    def attach(
        cls,
        entry: Any,
        *,
        on_enter: Optional[Callable[[], Any]] = None,
        select_on_focus: bool = True,
    ) -> None:
        """Configura cores e eventos sem assumir uma implementação gráfica."""
        if select_on_focus:
            cls.attach_focus(entry)
        else:
            cls.configure(entry)

        def _handle_enter(_event: Any = None) -> str:
            if on_enter is not None:
                on_enter()
            return cls.consume_enter()

        bind_enter_pair(
            entry,
            _handle_enter,
            owner="search-entry:enter",
        )

    @classmethod
    def attach_focus(cls, entry: Any) -> None:
        """Ativa texto digitável e seleciona a pesquisa anterior ao receber foco."""
        cls.configure(entry)
        bind_key_once(
            entry,
            "<FocusIn>",
            lambda event: cls.select_existing_text(event.widget),
            owner="search-entry:focus",
        )

    @classmethod
    def select_existing_text(cls, entry: Any) -> None:
        cls.configure(entry)
        value = str(entry.get() or "")
        if value:
            try:
                entry.select_range(0, "end")
            except (AttributeError, TypeError):
                try:
                    entry.selection_range(0, "end")
                except (AttributeError, TypeError):
                    pass
            try:
                entry.icursor("end")
            except (AttributeError, TypeError):
                pass
        # FocusIn não deve ser consumido: CTkEntry precisa concluir a própria
        # desativação do placeholder para a primeira tecla/leitura ser aceita.
        return None

    @classmethod
    def prepare_empty_input(cls, entry: Any, *, placeholder: str) -> None:
        """Muda o modo do campo sem depender do próximo evento ``FocusIn``.

        ``CTkEntry.set`` desativa seu placeholder pela API pública. Para widgets
        Tk compatíveis, a mesma transição é feita com ``delete``.
        """
        entry.configure(placeholder_text=placeholder)
        setter = getattr(entry, "set", None)
        if callable(setter):
            setter("")
        else:
            entry.delete(0, "end")
        entry.focus_set()
        try:
            entry.icursor(0)
        except (AttributeError, TypeError):
            pass

    @staticmethod
    def consume_enter() -> str:
        return "break"
