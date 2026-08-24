from __future__ import annotations

from commercial.application.action_dto import ActionContext, ActionOrigin


class ProductManagementService:
    """Porta administrativa: sessão, permissão e ator ficam fora da GUI."""

    def __init__(self, products, stock_actions, security, assisted_actions=None) -> None:
        if products is None or stock_actions is None or security is None:
            raise ValueError("Produtos, estoque e segurança são obrigatórios.")
        self.products = products
        self.stock_actions = stock_actions
        self.security = security
        self.assisted_actions = assisted_actions

    def _require(self, action: str) -> str:
        session = self.security.session
        if session is None or self.security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self.security.require("produtos", action):
            raise PermissionError("Usuário sem permissão para esta operação de produtos.")
        self.security.touch()
        return session.user.username

    def search(self, term: str, *, limit: int = 100):
        self._require("view")
        return tuple(self.products.search_products(term, limit=limit))

    def get(self, product_id: int):
        self._require("view")
        return self.products.get_product(int(product_id))

    def create(self, command):
        self._require("create")
        return self.products.create_product(command)

    def update(self, command):
        self._require("edit")
        return self.products.update_product(command)

    def stock(self, product_id: int):
        self._require("view")
        return self.products.product_stock(int(product_id))

    def movements(self, product_id: int, *, limit: int = 200):
        self._require("view")
        return tuple(self.products.product_movements(int(product_id), limit=limit))

    def low_stock(self):
        self._require("view")
        return tuple(self.products.low_stock_products())

    def receive(self, command, *, confirmed: bool):
        return self._stock_action("edit", command, confirmed, self.stock_actions.receive_stock)

    def remove(self, command, *, confirmed: bool):
        return self._stock_action("edit", command, confirmed, self.stock_actions.remove_stock)

    def adjust(self, command, *, confirmed: bool):
        return self._stock_action("edit", command, confirmed, self.stock_actions.adjust_stock)

    def _stock_action(self, permission, command, confirmed, operation):
        username = self._require(permission)
        context = ActionContext(username, ActionOrigin.UI)
        return operation(command, context=context, confirmed=bool(confirmed))

    def execute_assisted(
        self, operation: str, command, *, username: str,
        idempotency_key: str, operation_fingerprint: str,
    ):
        if self.assisted_actions is None:
            raise RuntimeError("Operações assistidas idempotentes não estão disponíveis.")
        operation = str(operation or "").upper()
        permission = "create" if operation == "PRODUCT_CREATE" else "edit"
        current = self._require(permission)
        if current != str(username or "").strip():
            raise PermissionError("A confirmação pertence a outro usuário.")
        if operation == "PRODUCT_CREATE":
            return self.assisted_actions.create_product(
                command, username=current, idempotency_key=idempotency_key,
                operation_fingerprint=operation_fingerprint,
            )
        return self.assisted_actions.move_stock(
            operation, command, username=current, idempotency_key=idempotency_key,
            operation_fingerprint=operation_fingerprint,
        )
