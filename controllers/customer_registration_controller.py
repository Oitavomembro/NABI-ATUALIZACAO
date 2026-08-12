from __future__ import annotations

from typing import Any

from services.customer_registration_service import CustomerRegistrationService


class CustomerRegistrationController:
    """Orquestra entrada de cadastro sem conhecer widgets ou persistência."""

    def __init__(self, service: CustomerRegistrationService) -> None:
        self.service = service

    def create(self, **data: Any) -> int:
        return self.service.criar(**data)
