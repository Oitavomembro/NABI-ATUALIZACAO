from __future__ import annotations


class AssistantOperationJournalRepository:
    """Persistência do diário da Nabi dentro da transação fornecida pelo serviço."""

    @staticmethod
    def get(connection, idempotency_key: str):
        row = connection.execute(
            "SELECT fingerprint,status,result_json FROM assistant_operation_journal "
            "WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return {
            "fingerprint": str(row[0]),
            "status": str(row[1]),
            "result_json": str(row[2] or "{}"),
        }

    @staticmethod
    def begin(
        connection, *, idempotency_key: str, operation_kind: str,
        fingerprint: str, username: str,
    ) -> None:
        connection.execute(
            """INSERT INTO assistant_operation_journal
               (idempotency_key,operation_kind,fingerprint,status,result_json,username,created_at)
               VALUES(?,?,?,'PENDING','',?,datetime('now','localtime'))""",
            (idempotency_key, operation_kind, fingerprint, username),
        )

    @staticmethod
    def commit(connection, *, idempotency_key: str, result_json: str) -> None:
        updated = connection.execute(
            """UPDATE assistant_operation_journal
               SET status='COMMITTED',result_json=?,committed_at=datetime('now','localtime')
               WHERE idempotency_key=? AND status='PENDING'""",
            (result_json, idempotency_key),
        )
        if updated.rowcount != 1:
            raise RuntimeError("Não foi possível confirmar o diário idempotente.")
