from __future__ import annotations


class ProductNcmCorrectionManagementService:
    """Porta administrativa estreita: leitura e correção NCM com sessão real."""

    def __init__(self, product_service, security_service, assisted_service) -> None:
        if product_service is None or security_service is None or assisted_service is None:
            raise ValueError("Produto, segurança e serviço assistido são obrigatórios.")
        self._products = product_service
        self._security = security_service
        self._assisted = assisted_service

    def _require(self, action: str) -> str:
        session = self._security.session
        if session is None or self._security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self._security.require("produtos", action):
            raise PermissionError("Usuário sem permissão para esta operação de produtos.")
        self._security.touch()
        return str(session.user.username)

    def get_product(self, product_id: int):
        self._require("view")
        return self._products.buscar(int(product_id))

    def correct_ncm(
        self, draft, *, username: str, idempotency_key: str,
        operation_fingerprint: str,
    ):
        current = self._require("edit")
        if current != str(username or "").strip():
            raise PermissionError("A confirmação pertence a outro usuário.")
        return self._assisted.correct_ncm(
            draft, username=current, idempotency_key=idempotency_key,
            operation_fingerprint=operation_fingerprint,
        )
