from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from .contracts import AssistantActor, CapabilityLevel


@dataclass(frozen=True, slots=True)
class ConfirmationChallenge:
    token: str
    draft_id: str
    fingerprint: str
    username: str
    session_id: str
    expires_at: datetime
    required_capability: CapabilityLevel


@dataclass(frozen=True, slots=True)
class ConfirmedDraftAuthorization:
    draft_id: str
    fingerprint: str
    username: str
    session_id: str
    confirmed_at: datetime
    capability: CapabilityLevel


class DraftConfirmationService:
    """Confirmação humana curta, de uso único e vinculada ao conteúdo exato."""

    def __init__(self, *, ttl_seconds: int = 120, clock=None) -> None:
        self._ttl = max(15, min(int(ttl_seconds), 300))
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._pending: dict[str, ConfirmationChallenge] = {}
        self._session_token: dict[str, str] = {}
        self._lock = Lock()

    def issue(self, draft, *, actor: AssistantActor) -> ConfirmationChallenge:
        if not self._is_confirmable(draft) or not isinstance(actor, AssistantActor):
            raise TypeError("Rascunho e operador autenticado são obrigatórios.")
        now = self._clock()
        challenge = ConfirmationChallenge(
            token=secrets.token_urlsafe(32),
            draft_id=draft.draft_id,
            fingerprint=draft.fingerprint,
            username=actor.username,
            session_id=actor.session_id,
            expires_at=now + timedelta(seconds=self._ttl),
            required_capability=(
                CapabilityLevel.REINFORCED_CONFIRMATION
                if draft.operation_kind == "PURCHASE_RECEIPT"
                else CapabilityLevel.SIMPLE_CONFIRMATION
            ),
        )
        with self._lock:
            previous = self._session_token.get(actor.session_id)
            if previous:
                self._pending.pop(previous, None)
            self._pending[challenge.token] = challenge
            self._session_token[actor.session_id] = challenge.token
        return challenge

    def confirm(
        self, *, token: str, draft, actor: AssistantActor
    ) -> ConfirmedDraftAuthorization:
        token = str(token or "")
        with self._lock:
            challenge = self._pending.pop(token, None)
            if challenge is not None:
                self._session_token.pop(challenge.session_id, None)
        if challenge is None:
            raise PermissionError("A confirmação não existe ou já foi utilizada.")
        now = self._clock()
        if now >= challenge.expires_at:
            raise PermissionError("A confirmação expirou.")
        if actor.username != challenge.username or actor.session_id != challenge.session_id:
            raise PermissionError("A confirmação pertence a outro usuário ou sessão.")
        if draft.draft_id != challenge.draft_id or not hmac.compare_digest(
            draft.fingerprint, challenge.fingerprint
        ):
            raise PermissionError("O rascunho mudou depois da revisão.")
        return ConfirmedDraftAuthorization(
            draft_id=draft.draft_id,
            fingerprint=draft.fingerprint,
            username=actor.username,
            session_id=actor.session_id,
            confirmed_at=now,
            capability=challenge.required_capability,
        )

    @staticmethod
    def _is_confirmable(draft) -> bool:
        return (
            isinstance(getattr(draft, "draft_id", None), str)
            and bool(draft.draft_id)
            and isinstance(getattr(draft, "fingerprint", None), str)
            and len(draft.fingerprint) == 64
            and isinstance(getattr(draft, "operation_kind", None), str)
            and bool(draft.operation_kind)
        )

    def invalidate_session(self, session_id: str) -> None:
        with self._lock:
            token = self._session_token.pop(str(session_id or ""), None)
            if token:
                self._pending.pop(token, None)
