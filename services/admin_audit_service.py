from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from repositories.admin_audit_repository import AdminAuditRepository
from core.sensitive_data import sanitize_text
from services.critical_audit_policy import is_critical_event


@dataclass(frozen=True)
class SecurityAuditEntry:
    date: str
    user: str
    action: str
    result: str
    details: str


class AdminAuditService:
    """Persistência de acessos administrativos e consulta da auditoria de segurança."""

    def __init__(self, connection_factory: Callable[[], object], logger: logging.Logger | None = None):
        self._connection_factory = connection_factory
        self._repository = AdminAuditRepository(connection_factory)
        self._logger = logger or logging.getLogger(__name__)


    def record_event(
        self,
        module: str,
        action: str,
        *,
        object_id: object = "",
        details: object = "",
        result: str = "SUCESSO",
        user: str = "Sistema",
        event_bus=None,
        events_enabled: bool = True,
        database_exists: bool = True,
    ) -> None:
        """Registra auditoria geral sem expor SQL ou política de eventos ao legado."""
        if is_critical_event(module, action):
            self.record_event_strict(
                module, action, object_id=object_id, details=details,
                result=result, user=user,
            )
            return
        safe_user, safe_object, safe_details = map(sanitize_text, (user, object_id, details))
        message = sanitize_text(
            f"AUDITORIA | usuário={safe_user} | módulo={module} | ação={action} | "
            f"objeto={safe_object} | resultado={result} | {safe_details}"
        )
        (self._logger.info if result == "SUCESSO" else self._logger.error)(message)
        if events_enabled and event_bus is not None:
            event_bus.publish(
                "auditoria.registrada",
                modulo=module, acao=action, objeto=safe_object, detalhes=safe_details,
                resultado=result, usuario=safe_user,
            )
        if not database_exists:
            return
        try:
            self._repository.record_event(
                occurred_at=datetime.now().isoformat(timespec="seconds"),
                user=safe_user,
                module=module,
                action=action,
                object_id=safe_object,
                details=safe_details,
                result=result,
            )
        except Exception:
            self._logger.exception("Não foi possível persistir a auditoria no banco.")

    def record_event_strict(
        self, module: str, action: str, *, object_id: object = "",
        details: object = "", result: str = "SUCESSO", user: str = "Sistema",
    ) -> None:
        """Persiste evento sensível ou propaga a falha para bloquear a operação."""

        persisted = self._repository.record_event(
            occurred_at=datetime.now().isoformat(timespec="seconds"),
            user=sanitize_text(user), module=str(module), action=str(action),
            object_id=sanitize_text(object_id), details=sanitize_text(details), result=str(result),
        )
        if not persisted:
            raise RuntimeError("Auditoria crítica indisponível: tabela auditoria ausente.")

    def record_admin_access(self, success: bool, details: str, *, occurred_at: str | None = None) -> None:
        text = sanitize_text(details or "").strip()
        if not text:
            raise ValueError("Os detalhes do acesso administrativo são obrigatórios.")
        try:
            self._repository.record_admin_access(
                occurred_at=occurred_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                success=success,
                details=text,
            )
        except Exception:
            self._logger.exception("Falha ao registrar acesso administrativo")
            raise

    def list_security_audit(self, limit: int = 500) -> list[SecurityAuditEntry]:
        safe_limit = max(1, min(int(limit), 5000))
        rows = self._repository.list_security_audit(safe_limit)
        return [
            SecurityAuditEntry(
                date=str(row[0] or ""),
                user=sanitize_text(row[1] or ""),
                action=str(row[2] or ""),
                result=str(row[3] or ""),
                details=sanitize_text(row[4] or ""),
            )
            for row in rows
        ]
