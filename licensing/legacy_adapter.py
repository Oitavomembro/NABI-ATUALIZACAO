from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from .models import LicenseState
from .runtime import build_runtime_license_service


@dataclass(frozen=True, slots=True)
class LegacyLicenseStatus:
    blocked: bool
    days_remaining: int | None = None
    reason: str = ""
    invalid_value: bool = False


class LegacyLicenseV2Adapter:
    """Compatibilidade visual; toda decisão continua pertencendo ao V2."""

    def __init__(self, app_dir=None, *, service=None) -> None:
        directory = app_dir or os.environ.get("NABICODE_APP_DIR", "")
        self._service = service or build_runtime_license_service(directory)

    def evaluate(self) -> LegacyLicenseStatus:
        decision = self._service.evaluate()
        days = decision.grace_days_remaining
        if decision.state is LicenseState.ACTIVE and decision.payload is not None:
            days = max(
                0,
                (decision.payload.valid_until - datetime.now(timezone.utc).date()).days,
            )
        return LegacyLicenseStatus(
            blocked=not decision.operational,
            days_remaining=days,
            reason=f"{decision.state.value}:{decision.reason}",
            invalid_value=decision.state is LicenseState.INVALID,
        )

    def monitor_exact_expiration(self) -> LegacyLicenseStatus:
        return self.evaluate()

    @staticmethod
    def unlock_for_days(_days: int = 30) -> str:
        raise PermissionError("Licença V2 exige documento .nabilic assinado.")

    @staticmethod
    def attempt_admin_unlock(*_args, **_kwargs) -> bool:
        return False
