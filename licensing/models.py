from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
import re
import uuid


class LicenseState(str, Enum):
    ACTIVE = "ATIVA"
    GRACE = "TOLERANCIA"
    BLOCKED = "BLOQUEADA"
    INVALID = "INVALIDA"
    CLOCK_SUSPECT = "RELOGIO_SUSPEITO"
    REVOKED = "REVOGADA"


class LicenseEdition(str, Enum):
    COMMERCIAL = "COMERCIAL"
    EVALUATION = "AVALIACAO"


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_FEATURE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


@dataclass(frozen=True, slots=True)
class LicensePayload:
    schema: int
    license_id: str
    edition: LicenseEdition
    customer_name: str
    machine_fingerprint: str
    issued_at: datetime
    valid_until: date
    grace_days: int
    features: tuple[str, ...]
    revoked: bool = False

    FORMAT_SCHEMA = 2
    NORMATIVE_GRACE_DAYS = 10
    EVALUATION_MAX_DAYS = 30

    def __post_init__(self) -> None:
        if int(self.schema) != self.FORMAT_SCHEMA:
            raise ValueError("Schema de licença incompatível.")
        normalized_id = str(uuid.UUID(str(self.license_id)))
        customer = str(self.customer_name or "").strip()
        if not customer or len(customer) > 160:
            raise ValueError("Titular da licença inválido.")
        fingerprint = str(self.machine_fingerprint).strip().lower()
        if not _HEX_64.fullmatch(fingerprint):
            raise ValueError("Fingerprint de máquina inválido.")
        issued = self.issued_at
        if issued.tzinfo is None or issued.utcoffset() is None:
            raise ValueError("Data de emissão deve possuir fuso horário.")
        issued = issued.astimezone(timezone.utc).replace(microsecond=0)
        if self.valid_until < issued.date():
            raise ValueError("Validade anterior à emissão.")
        if int(self.grace_days) != self.NORMATIVE_GRACE_DAYS:
            raise ValueError("A tolerância assinada deve ser de dez dias.")
        normalized_features = tuple(sorted({str(item).strip().lower() for item in self.features}))
        if not normalized_features or any(not _FEATURE.fullmatch(item) for item in normalized_features):
            raise ValueError("Recursos da licença inválidos.")
        if self.edition is LicenseEdition.EVALUATION:
            duration = (self.valid_until - issued.date()).days + 1
            if duration > self.EVALUATION_MAX_DAYS:
                raise ValueError("A edição AVALIAÇÃO não pode exceder trinta dias.")
        object.__setattr__(self, "license_id", normalized_id)
        object.__setattr__(self, "customer_name", customer)
        object.__setattr__(self, "machine_fingerprint", fingerprint)
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "grace_days", int(self.grace_days))
        object.__setattr__(self, "features", normalized_features)


@dataclass(frozen=True, slots=True)
class LicenseDecision:
    state: LicenseState
    reason: str
    machine_code: str
    payload: LicensePayload | None = None
    grace_days_remaining: int | None = None

    @property
    def operational(self) -> bool:
        return self.state in {LicenseState.ACTIVE, LicenseState.GRACE}
