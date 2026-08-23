from __future__ import annotations

from .ports import ProductCatalogPort, StockReadPort


class ProductApplicationService:
    """Fachada de produtos/estoque somente por contratos comerciais."""

    def __init__(self, catalog: ProductCatalogPort, stock: StockReadPort) -> None:
        self._catalog = catalog
        self._stock = stock

    def create_product(self, command):
        return self._catalog.create(command)

    def update_product(self, command):
        return self._catalog.update(command)

    def get_product(self, product_id: int):
        product = self._catalog.get_details(product_id)
        if product is None:
            raise ValueError("Produto não encontrado.")
        return product

    def search_products(self, term: str, *, limit: int = 30):
        return self._catalog.search_details(term, limit=limit)

    def get_product_by_barcode(self, barcode: str):
        return self._catalog.get_by_barcode(barcode)

    def product_stock(self, product_id: int):
        return self._stock.stock(product_id)

    def product_movements(self, product_id: int, *, limit: int = 200):
        return self._stock.movements(product_id, limit=limit)

    def low_stock_products(self):
        return self._stock.low_stock()
