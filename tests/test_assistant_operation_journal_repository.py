import sqlite3

import pytest

from repositories.assistant_operation_journal_repository import (
    AssistantOperationJournalRepository,
)


def connection():
    database = sqlite3.connect(":memory:")
    database.execute("""CREATE TABLE assistant_operation_journal(
        idempotency_key TEXT PRIMARY KEY, operation_kind TEXT, fingerprint TEXT,
        status TEXT, result_json TEXT, username TEXT, created_at TEXT,
        committed_at TEXT
    )""")
    return database


def test_diario_inicia_consulta_e_confirma_na_mesma_conexao():
    database = connection()
    repository = AssistantOperationJournalRepository()
    repository.begin(
        database, idempotency_key="op-1", operation_kind="CUSTOMER_RECEIPT",
        fingerprint="a" * 64, username="maria",
    )
    assert repository.get(database, "op-1")["status"] == "PENDING"
    repository.commit(database, idempotency_key="op-1", result_json='{"id":1}')
    assert repository.get(database, "op-1") == {
        "fingerprint": "a" * 64, "status": "COMMITTED", "result_json": '{"id":1}',
    }
    database.close()


def test_diario_nao_confirma_duas_vezes():
    database = connection()
    repository = AssistantOperationJournalRepository()
    repository.begin(
        database, idempotency_key="op-1", operation_kind="CUSTOMER_RECEIPT",
        fingerprint="a" * 64, username="maria",
    )
    repository.commit(database, idempotency_key="op-1", result_json="{}")
    with pytest.raises(RuntimeError, match="diário idempotente"):
        repository.commit(database, idempotency_key="op-1", result_json="{}")
    database.close()
