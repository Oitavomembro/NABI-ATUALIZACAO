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

    def create_products_from_xml(self, commands, **context):
        """Cria somente cadastros; a infraestrutura mantém lote e auditoria atômicos."""
        operation = getattr(self._catalog, "create_products_from_xml", None)
        if operation is None:
            raise RuntimeError("Importação cadastral por XML não está disponível.")
        return operation(tuple(commands), **context)

    def get_product(self, product_id: int):
        product = self._catalog.get_details(product_id)
        if product is None:
            raise ValueError("Produto não encontrado.")
        return product

    def search_products(self, term: str, *, limit: int = 30):
        return self._catalog.search_details(term, limit=limit)

    def get_product_by_barcode(self, barcode: str):
        return self._catalog.get_by_barcode(barcode)

    def list_units(self):
        operation = getattr(self._catalog, "list_units", None)
        return tuple(operation() if operation else ())

    def product_stock(self, product_id: int):
        return self._stock.stock(product_id)

    def product_movements(self, product_id: int, *, limit: int = 200):
        return self._stock.movements(product_id, limit=limit)

    def low_stock_products(self):
        return self._stock.low_stock()

    def high_stock_products(self, *, limit: int = 20):
        """Lista produtos vendáveis priorizando saldo, sem expor persistência."""
        safe_limit = max(1, min(int(limit), 100))
        products = self._catalog.search_details("", limit=200)
        eligible = (
            product for product in products
            if product.active
            and product.sale_price > 0
            and product.current_stock > 0
            and str(product.product_type or "").upper() != "SERVICO"
        )
        return tuple(sorted(
            eligible,
            key=lambda product: (
                -product.current_stock,
                product.description.casefold(),
                product.product_id,
            ),
        )[:safe_limit])
