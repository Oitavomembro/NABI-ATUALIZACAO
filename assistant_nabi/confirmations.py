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
class _GrantRecord:
    draft_id: str
    fingerprint: str
    operation: str
    username: str
    session_id: str
    confirmed_at: datetime
    expires_at: datetime
    capability: CapabilityLevel


class ConfirmedDraftAuthorization:
    """Handle opaco. Só o broker que o emitiu pode validá-lo e consumi-lo."""

    __slots__ = ("__broker", "__nonce")

    def __new__(cls, *args, **kwargs):
        raise TypeError("Autorizações só podem ser emitidas pelo broker de confirmação.")

    @classmethod
    def _issued(cls, broker, nonce: str):
        instance = object.__new__(cls)
        instance.__broker = broker
        instance.__nonce = nonce
        return instance

    def consume(self, draft, *, operation: str, actor: AssistantActor | None = None):
        return self.__broker.consume(self, draft=draft, operation=operation, actor=actor)

    @property
    def fingerprint(self):
        return self.__broker.describe(self).fingerprint

    @property
    def session_id(self):
        return self.__broker.describe(self).session_id

    @property
    def capability(self):
        return self.__broker.describe(self).capability


class DraftConfirmationService:
    """Confirmação humana curta, de uso único e vinculada ao conteúdo exato."""

    def __init__(self, *, ttl_seconds: int = 120, clock=None) -> None:
        self._ttl = max(15, min(int(ttl_seconds), 300))
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._pending: dict[str, ConfirmationChallenge] = {}
        self._session_token: dict[str, str] = {}
        self._grants: dict[str, _GrantRecord] = {}
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
                if draft.operation_kind in {"PURCHASE_RECEIPT", "NFE_ENTRY_IMPORT"}
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
        record = _GrantRecord(
            draft_id=draft.draft_id,
            fingerprint=draft.fingerprint,
            operation=draft.operation_kind,
            username=actor.username,
            session_id=actor.session_id,
            confirmed_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
            capability=challenge.required_capability,
        )
        nonce = secrets.token_urlsafe(32)
        with self._lock:
            self._grants[nonce] = record
        return ConfirmedDraftAuthorization._issued(self, nonce)

    def consume(self, grant, *, draft, operation: str, actor=None) -> _GrantRecord:
        if not isinstance(grant, ConfirmedDraftAuthorization):
            raise PermissionError("A autorização não foi emitida pelo broker.")
        try:
            broker = grant._ConfirmedDraftAuthorization__broker
            nonce = grant._ConfirmedDraftAuthorization__nonce
        except AttributeError as error:
            raise PermissionError("A autorização é inválida.") from error
        if broker is not self:
            raise PermissionError("A autorização pertence a outro broker.")
        with self._lock:
            record = self._grants.get(nonce)
        if record is None:
            raise PermissionError("A autorização não existe ou já foi utilizada.")
        if self._clock() >= record.expires_at:
            with self._lock:
                self._grants.pop(nonce, None)
            raise PermissionError("A autorização expirou.")
        if operation != record.operation or getattr(draft, "operation_kind", None) != operation:
            raise PermissionError("A autorização pertence a outra operação.")
        if draft.draft_id != record.draft_id or not hmac.compare_digest(
            draft.fingerprint, record.fingerprint
        ):
            raise PermissionError("A autorização pertence a outro conteúdo.")
        if actor is not None and (
            actor.username != record.username or actor.session_id != record.session_id
        ):
            raise PermissionError("A autorização pertence a outro usuário ou sessão.")
        required = (
            CapabilityLevel.REINFORCED_CONFIRMATION
            if operation in {"PURCHASE_RECEIPT", "NFE_ENTRY_IMPORT"}
            else CapabilityLevel.SIMPLE_CONFIRMATION
        )
        if record.capability is not required:
            raise PermissionError("A autorização não possui a capacidade exigida.")
        with self._lock:
            if self._grants.pop(nonce, None) is not record:
                raise PermissionError("A autorização não existe ou já foi utilizada.")
        return record

    def describe(self, grant) -> _GrantRecord:
        try:
            broker = grant._ConfirmedDraftAuthorization__broker
            nonce = grant._ConfirmedDraftAuthorization__nonce
        except AttributeError as error:
            raise PermissionError("A autorização é inválida.") from error
        if broker is not self:
            raise PermissionError("A autorização pertence a outro broker.")
        with self._lock:
            record = self._grants.get(nonce)
        if record is None:
            raise PermissionError("A autorização não existe ou já foi utilizada.")
        return record

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
        session_id = str(session_id or "")
        with self._lock:
            token = self._session_token.pop(session_id, None)
            if token:
                self._pending.pop(token, None)
            for nonce, record in tuple(self._grants.items()):
                if record.session_id == session_id:
                    self._grants.pop(nonce, None)
