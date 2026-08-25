from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountantDeliveryPlan:
    package_path: str
    package_sha256: str
    cnpj: str
    competence: str
    profile: str
    recipient: str
    destination: str
    reviewed_by: str
    idempotency_key: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class AccountantDeliveryStatus:
    idempotency_key: str
    status: str
    attempts: int
    transport_reference: str = ""
    receipt_sha256: str = ""
    last_error_code: str = ""
