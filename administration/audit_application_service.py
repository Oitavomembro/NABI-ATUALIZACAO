from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditPage:
    entries: tuple
    limit: int


class AuditApplicationService:
    """Consulta administrativa fail-closed da auditoria de segurança."""

    def __init__(self, audit_service, security) -> None:
        self.audit_service = audit_service
        self.security = security

    def load(self, *, limit: int = 500) -> AuditPage:
        session = getattr(self.security, "session", None)
        if session is None or self.security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self.security.require("technical", "audit"):
            raise PermissionError("Seu perfil não possui acesso à auditoria administrativa.")
        safe_limit = max(1, min(int(limit), 500))
        self.security.touch()
        return AuditPage(tuple(self.audit_service.list_security_audit(safe_limit)), safe_limit)
