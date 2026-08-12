from __future__ import annotations

from typing import Callable, Iterable

from database.sqlite_introspection import table_exists


class AdminAuditRepository:
    def __init__(self, connection_factory: Callable[[], object]) -> None:
        self._connection_factory = connection_factory

    def record_event(
        self,
        *,
        occurred_at: str,
        user: str,
        module: str,
        action: str,
        object_id: str,
        details: str,
        result: str,
    ) -> bool:
        connection = self._connection_factory()
        try:
            if not table_exists(connection, "auditoria"):
                return False
            connection.execute(
                """INSERT INTO auditoria (data, usuario, modulo, acao, objeto, detalhes, resultado)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (occurred_at, user, module, action, object_id, details, result),
            )
            connection.commit()
            return True
        except Exception:
            try:
                connection.rollback()
            finally:
                raise
        finally:
            connection.close()

    def record_admin_access(self, *, occurred_at: str, success: bool, details: str) -> None:
        connection = self._connection_factory()
        try:
            connection.execute(
                "INSERT INTO log_acesso_admin (data, sucesso, detalhes) VALUES (?, ?, ?)",
                (occurred_at, 1 if success else 0, details),
            )
            connection.commit()
        except Exception:
            try:
                connection.rollback()
            finally:
                raise
        finally:
            connection.close()

    def list_security_audit(self, limit: int) -> Iterable[tuple]:
        connection = self._connection_factory()
        try:
            return connection.execute(
                """SELECT data, usuario, acao, resultado, detalhes
                   FROM auditoria
                   WHERE modulo='SEGURANCA'
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            connection.close()
