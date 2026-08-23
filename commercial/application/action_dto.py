from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class ActionOrigin(str, Enum):
    UI = "UI"
    AI = "IA"
    SYSTEM = "SISTEMA"


class ActionSensitivity(str, Enum):
    REVERSIBLE = "REVERSIVEL"
    SENSITIVE = "SENSIVEL"
    CRITICAL = "CRITICA"


@dataclass(frozen=True, slots=True)
class ActionContext:
    requested_by: str
    origin: ActionOrigin
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        actor = str(self.requested_by or "").strip()
        if not actor:
            raise ValueError("O solicitante da ação é obrigatório.")
        origin = self.origin if isinstance(self.origin, ActionOrigin) else ActionOrigin(self.origin)
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at deve possuir fuso horário.")
        object.__setattr__(self, "requested_by", actor)
        object.__setattr__(self, "origin", origin)


@dataclass(frozen=True, slots=True)
class CommercialActionResult:
    action: str
    context: ActionContext
    sensitivity: ActionSensitivity
    requires_human_confirmation: bool
    executed: bool
    committed: bool
    message: str
    resource_id: int | None = None
    secondary_effect_failed: bool = False


@dataclass(frozen=True, slots=True)
class PersistedCancellation:
    sale_id: int
    status: str = "CANCELADO"


@dataclass(frozen=True, slots=True)
class SaleCancelled:
    sale_id: int
    context: ActionContext
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
