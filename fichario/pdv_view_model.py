from __future__ import annotations

from ui_qt.commercial.pdv_view_model import CheckoutInput, PDVViewModel


class FicharioPDVViewModel(PDVViewModel):
    """Política da edição: somente avulso e compra sempre ligada a ficha real."""

    def search_products(self, term: str, *, limit: int = 30):
        return ()

    def select_product(self, product_id: int):
        raise PermissionError("A edição Fichário não utiliza cadastro de produtos.")

    def add_selected_product(self, quantity: str) -> None:
        raise PermissionError("A edição Fichário aceita somente produto avulso.")

    def select_final_consumer(self):
        raise ValueError("Selecione uma ficha de cliente para registrar a compra.")

    def checkout(self, data: CheckoutInput, *, user: str):
        customer = self.selected_customer
        if customer is None or customer.code.strip().upper() == "CONSUMIDOR_FINAL":
            raise ValueError("Selecione uma ficha de cliente antes de finalizar a compra.")
        if any(item.product_id is not None for item in self.session.cart.items):
            raise PermissionError("O Fichário não permite itens do catálogo de produtos.")
        return super().checkout(data, user=user)
