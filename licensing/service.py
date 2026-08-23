from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping

from .license_format import verify_envelope
from .machine import machine_code
from .models import LicenseDecision, LicensePayload, LicenseState
from .storage import ProtectedStateStore, atomic_write


class LicenseV2Service:
    """Verifica, ativa e monitora licenças assinadas sem consultar o banco."""

    CLOCK_ROLLBACK_TOLERANCE = timedelta(minutes=5)

    def __init__(
        self,
        *,
        license_path: str | Path,
        state_store: ProtectedStateStore,
        public_keys: Mapping[str, bytes],
        machine_fingerprint: Callable[[], str],
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.license_path = Path(license_path)
        self.state_store = state_store
        self.public_keys = dict(public_keys)
        self._machine_fingerprint = machine_fingerprint
        self._now = now

    def _current(self) -> datetime:
        current = self._now()
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("Relógio sem fuso horário.")
        return current.astimezone(timezone.utc).replace(microsecond=0)

    def _fingerprint(self) -> tuple[str, str]:
        fingerprint = self._machine_fingerprint()
        return fingerprint, machine_code(fingerprint)

    def _invalid(self, reason: str, code: str = "NABI2-INDISPONIVEL") -> LicenseDecision:
        return LicenseDecision(LicenseState.INVALID, reason, code)

    def _load_payload(self) -> LicensePayload:
        return verify_envelope(self.license_path.read_bytes(), self.public_keys)

    @staticmethod
    def _state_for(payload: LicensePayload, fingerprint: str, current: datetime) -> dict:
        return {
            "license_id": payload.license_id,
            "machine_fingerprint": fingerprint,
            "last_seen": current.isoformat().replace("+00:00", "Z"),
            "highest_issued_at": payload.issued_at.isoformat().replace("+00:00", "Z"),
            "highest_valid_until": payload.valid_until.isoformat(),
        }

    def activate(self, source: str | Path) -> LicenseDecision:
        """Importa uma licença verificada; senha local nunca participa da decisão."""
        source_path = Path(source)
        raw = source_path.read_bytes()
        payload = verify_envelope(raw, self.public_keys)
        current = self._current()
        fingerprint, code = self._fingerprint()
        if not hmac.compare_digest(payload.machine_fingerprint, fingerprint):
            return LicenseDecision(LicenseState.INVALID, "MACHINE_MISMATCH", code)

        previous = None
        try:
            previous = self.state_store.read()
        except FileNotFoundError:
            pass
        if previous is not None:
            highest_issued = datetime.fromisoformat(
                str(previous["highest_issued_at"]).replace("Z", "+00:00")
            )
            highest_valid = str(previous["highest_valid_until"])
            if payload.issued_at < highest_issued or (
                not payload.revoked and payload.valid_until.isoformat() < highest_valid
            ):
                return LicenseDecision(LicenseState.INVALID, "LICENSE_ROLLBACK", code)

        atomic_write(self.license_path, raw)
        self.state_store.write(self._state_for(payload, fingerprint, current))
        return self.evaluate()

    def evaluate(self) -> LicenseDecision:
        try:
            fingerprint, code = self._fingerprint()
        except Exception:
            return self._invalid("MACHINE_ID_UNAVAILABLE")
        try:
            payload = self._load_payload()
        except FileNotFoundError:
            return self._invalid("LICENSE_MISSING", code)
        except Exception:
            return self._invalid("LICENSE_INVALID", code)
        if not hmac.compare_digest(payload.machine_fingerprint, fingerprint):
            return self._invalid("MACHINE_MISMATCH", code)
        try:
            state = self.state_store.read()
        except FileNotFoundError:
            return self._invalid("PROTECTED_STATE_MISSING", code)
        except Exception:
            return self._invalid("PROTECTED_STATE_INVALID", code)
        if (
            str(state.get("license_id")) != payload.license_id
            or not hmac.compare_digest(str(state.get("machine_fingerprint")), fingerprint)
        ):
            return self._invalid("PROTECTED_STATE_MISMATCH", code)
        try:
            current = self._current()
            last_seen = datetime.fromisoformat(str(state["last_seen"]).replace("Z", "+00:00"))
            highest_issued = datetime.fromisoformat(
                str(state["highest_issued_at"]).replace("Z", "+00:00")
            )
            highest_valid = str(state["highest_valid_until"])
        except Exception:
            return self._invalid("PROTECTED_STATE_INVALID", code)
        if current + self.CLOCK_ROLLBACK_TOLERANCE < last_seen:
            return LicenseDecision(LicenseState.CLOCK_SUSPECT, "CLOCK_ROLLBACK", code, payload)
        if payload.issued_at < highest_issued or (
            not payload.revoked and payload.valid_until.isoformat() < highest_valid
        ):
            return self._invalid("LICENSE_ROLLBACK", code)
        if payload.revoked:
            return LicenseDecision(LicenseState.REVOKED, "SIGNED_REVOCATION", code, payload)

        today = current.date()
        grace_end = payload.valid_until + timedelta(days=payload.grace_days)
        if today <= payload.valid_until:
            state_name = LicenseState.ACTIVE
            reason = "VALID"
            remaining = None
        elif today <= grace_end:
            state_name = LicenseState.GRACE
            reason = "GRACE_PERIOD"
            remaining = (grace_end - today).days + 1
        else:
            state_name = LicenseState.BLOCKED
            reason = "EXPIRED"
            remaining = 0
        updated = dict(state)
        updated["last_seen"] = max(current, last_seen).isoformat().replace("+00:00", "Z")
        updated["highest_issued_at"] = max(payload.issued_at, highest_issued).isoformat().replace(
            "+00:00", "Z"
        )
        updated["highest_valid_until"] = max(payload.valid_until.isoformat(), highest_valid)
        try:
            self.state_store.write(updated)
        except Exception:
            return self._invalid("PROTECTED_STATE_UNWRITABLE", code)
        return LicenseDecision(state_name, reason, code, payload, remaining)
