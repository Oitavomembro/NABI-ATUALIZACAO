from __future__ import annotations

from typing import Any, Callable, Optional


class PDVEnterController:
    """Controla exclusivamente Enter/KP_Enter no fluxo principal do PDV."""

    def __init__(
        self,
        *,
        product_entry: Any,
        quantity_entry: Any,
        price_entry: Any,
        cart: Any,
        popup_getter: Callable[[], Any],
        confirm_suggestion: Callable[[Any], Any],
        select_by_barcode: Callable[[str], bool],
        add_item: Callable[[], Any],
        finalize_sale: Callable[[], Any],
        validate_quantity: Callable[[], bool],
        validate_price: Callable[[], bool],
    ) -> None:
        self.product_entry = product_entry
        self.quantity_entry = quantity_entry
        self.price_entry = price_entry
        self.cart = cart
        self.popup_getter = popup_getter
        self.confirm_suggestion = confirm_suggestion
        self.select_by_barcode = select_by_barcode
        self.add_item = add_item
        self.finalize_sale = finalize_sale
        self.validate_quantity = validate_quantity
        self.validate_price = validate_price

    @staticmethod
    def _focus(widget: Any) -> None:
        try:
            widget.focus_set()
        except Exception:
            return
        for method in ("select_range", "selection_range"):
            try:
                getattr(widget, method)(0, "end")
                break
            except Exception:
                continue

    @staticmethod
    def _popup_open(popup: Any) -> bool:
        if popup is None:
            return False
        try:
            return bool(popup.winfo_exists())
        except Exception:
            return False

    def handle_product(self, event: Any = None) -> str:
        if self._popup_open(self.popup_getter()):
            # O evento veio do campo de pesquisa, não da Treeview. Repassar
            # coordenadas desse evento para a tabela fazia o Enter identificar
            # uma linha inexistente e ignorar a sugestão selecionada.
            self.confirm_suggestion(None)
            return "break"

        term = str(self.product_entry.get() or "").strip()
        if not term:
            # Carrinho preenchido + pesquisa vazia: Enter desloca o foco para
            # a etapa de finalização. O próximo Enter no carrinho finaliza.
            try:
                if self.cart.get_children():
                    self._focus(self.cart)
            except Exception:
                pass
            return "break"
        if self.select_by_barcode(term):
            self._focus(self.quantity_entry)
            return "break"

        # Produto digitado sem seleção permanece no campo; a lista de sugestões
        # continua sendo o mecanismo oficial de seleção.
        return "break"

    def handle_quantity(self, _event: Any = None) -> str:
        if self.validate_quantity():
            self._focus(self.price_entry)
        else:
            self._focus(self.quantity_entry)
        return "break"

    def handle_price(self, _event: Any = None) -> str:
        if not self.validate_price():
            self._focus(self.price_entry)
            return "break"
        self.add_item()
        return "break"

    def handle_cart(self, _event: Any = None) -> str:
        self.finalize_sale()
        return "break"

    def handle_suggestion(self, event: Any = None) -> str:
        self.confirm_suggestion(event)
        return "break"

    @staticmethod
    def _bind_enter(widget: Any, callback: Callable[[Any], str]) -> None:
        widget.bind("<Return>", callback)
        widget.bind("<KP_Enter>", callback)

    def install(self) -> "PDVEnterController":
        self._bind_enter(self.product_entry, self.handle_product)
        self._bind_enter(self.quantity_entry, self.handle_quantity)
        self._bind_enter(self.price_entry, self.handle_price)
        self._bind_enter(self.cart, self.handle_cart)
        return self

    def bind_suggestion_table(self, table: Any) -> None:
        self._bind_enter(table, self.handle_suggestion)

    def dispatch_legacy_event(self, event: Any = None) -> Optional[str]:
        widget = getattr(event, "widget", None) if event is not None else None
        if widget is self.product_entry:
            return self.handle_product(event)
        if widget is self.quantity_entry:
            return self.handle_quantity(event)
        if widget is self.price_entry:
            return self.handle_price(event)
        if widget is self.cart:
            return self.handle_cart(event)
        return None
