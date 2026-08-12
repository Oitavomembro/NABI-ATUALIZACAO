from __future__ import annotations

from services.product_application_service import (
    ProductApplicationService,
    ProductFormData,
    ProductSaveResult,
)


class ProductRegistrationController:
    """Converte dados de cadastro em comando e delega a transação ao Service."""

    def __init__(self, service: ProductApplicationService) -> None:
        self.service = service

    def save(self, data: ProductFormData) -> ProductSaveResult:
        command = self.service.criar_comando(data)
        return self.service.salvar(command)
