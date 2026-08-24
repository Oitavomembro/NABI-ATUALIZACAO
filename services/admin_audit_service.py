from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from repositories.admin_audit_repository import AdminAuditRepository


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
        message = (
            f"AUDITORIA | usuário={user} | módulo={module} | ação={action} | "
            f"objeto={object_id} | resultado={result} | {details}"
        )
        (self._logger.info if result == "SUCESSO" else self._logger.error)(message)
        if events_enabled and event_bus is not None:
            event_bus.publish(
                "auditoria.registrada",
                modulo=module, acao=action, objeto=object_id, detalhes=details,
                resultado=result, usuario=user,
            )
        if not database_exists:
            return
        try:
            self._repository.record_event(
                occurred_at=datetime.now().isoformat(timespec="seconds"),
                user=user,
                module=module,
                action=action,
                object_id=str(object_id),
                details=str(details),
                result=result,
            )
        except Exception:
            self._logger.exception("Não foi possível persistir a auditoria no banco.")

    def record_event_strict(
        self, module: str, action: str, *, object_id: object = "",
        details: object = "", result: str = "SUCESSO", user: str = "Sistema",
    ) -> None:
        """Persiste evento sensível ou propaga a falha para bloquear a operação."""

        self._repository.record_event(
            occurred_at=datetime.now().isoformat(timespec="seconds"),
            user=str(user), module=str(module), action=str(action),
            object_id=str(object_id), details=str(details), result=str(result),
        )

    def record_admin_access(self, success: bool, details: str, *, occurred_at: str | None = None) -> None:
        text = str(details or "").strip()
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
                user=str(row[1] or ""),
                action=str(row[2] or ""),
                result=str(row[3] or ""),
                details=str(row[4] or ""),
            )
            for row in rows
        ]
