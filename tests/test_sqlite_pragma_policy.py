from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from database.sqlite_connection import (
    SQLitePragmaPolicyError, configure_connection, connection_session,
    effective_pragmas, open_connection,
)


def test_local_network_memory_and_legacy_profiles(tmp_path):
    local=tmp_path/"legacy.db"
    raw=sqlite3.connect(local); raw.execute("CREATE TABLE legacy(id INTEGER)"); raw.commit(); raw.close()
    connection=open_connection(local,timeout=1)
    try:
        assert effective_pragmas(connection) == {"foreign_keys":1,"journal_mode":"wal","synchronous":1,"busy_timeout":1000,"query_only":0}
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='legacy'").fetchone()[0]=="legacy"
    finally: connection.close()
    network=open_connection(local,timeout=2,network_mode=True)
    try:
        values=effective_pragmas(network); assert values["journal_mode"]=="delete" and values["synchronous"]==2 and values["busy_timeout"]==2000
    finally: network.close()
    memory=open_connection(":memory:")
    try:
        values=effective_pragmas(memory); assert values["journal_mode"]=="memory" and values["synchronous"]==1
    finally: memory.close()


def test_read_only_and_diagnostic_never_pretend_writability(tmp_path):
    path=tmp_path/"readonly.db"; raw=sqlite3.connect(path); raw.execute("CREATE TABLE data(value TEXT)"); raw.commit(); raw.close()
    readonly=open_connection(path,read_only=True)
    try:
        assert effective_pragmas(readonly)["query_only"]==1
        with pytest.raises(sqlite3.OperationalError): readonly.execute("INSERT INTO data VALUES('blocked')")
    finally: readonly.close()
    diagnostic=open_connection(path,apply_journal=False)
    try:
        assert effective_pragmas(diagnostic)["query_only"]==1
        with pytest.raises(sqlite3.OperationalError): diagnostic.execute("DELETE FROM data")
    finally: diagnostic.close()
    with pytest.raises(SQLitePragmaPolicyError,match="não pode ser aberta como escrita"):
        with connection_session(path,read_only=True,write=True): pass
    with pytest.raises(SQLitePragmaPolicyError,match="não pode ser aberta como escrita"):
        with connection_session(path,apply_journal=False,write=True): pass


class RefusingConnection:
    def __init__(self, base, *, refuse="", ignore=""):
        self.base=base; self.refuse=refuse; self.ignore=ignore; self.closed=False
    def execute(self, sql, parameters=()):
        normalized=" ".join(str(sql).upper().split())
        if self.refuse and self.refuse in normalized: raise sqlite3.OperationalError("pragma recusado")
        if self.ignore and self.ignore in normalized and "=" in normalized:
            return self.base.execute(normalized.split("=")[0])
        return self.base.execute(sql,parameters)
    def close(self): self.closed=True; self.base.close()
    @property
    def row_factory(self): return self.base.row_factory
    @row_factory.setter
    def row_factory(self,value): self.base.row_factory=value


def test_refused_pragma_fails_closed_with_actionable_message():
    wrapped=RefusingConnection(sqlite3.connect(":memory:"),refuse="PRAGMA FOREIGN_KEYS=ON")
    with pytest.raises(SQLitePragmaPolicyError,match="foi possível garantir.*não foi liberado"):
        configure_connection(wrapped)
    assert wrapped.base.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]==0


@pytest.mark.parametrize("ignored",["PRAGMA FOREIGN_KEYS=ON","PRAGMA SYNCHRONOUS=NORMAL","PRAGMA BUSY_TIMEOUT=30000"])
def test_effective_value_divergence_is_detected(ignored):
    wrapped=RefusingConnection(sqlite3.connect(":memory:"),ignore=ignored)
    with pytest.raises(SQLitePragmaPolicyError,match="esperado=.*efetivo="):
        configure_connection(wrapped)


def test_journal_and_readonly_divergence_are_detected(tmp_path):
    wrapped=RefusingConnection(sqlite3.connect(tmp_path/"journal.db"),ignore="PRAGMA JOURNAL_MODE=WAL")
    with pytest.raises(SQLitePragmaPolicyError,match="journal_mode"):
        configure_connection(wrapped)
    readonly=RefusingConnection(sqlite3.connect(":memory:"),ignore="PRAGMA QUERY_ONLY=ON")
    with pytest.raises(SQLitePragmaPolicyError,match="query_only"):
        configure_connection(readonly,read_only=True)


def test_open_connection_closes_handle_before_returning_on_policy_failure(tmp_path,monkeypatch):
    base=sqlite3.connect(tmp_path/"closed.db"); wrapped=RefusingConnection(base,refuse="PRAGMA FOREIGN_KEYS=ON")
    monkeypatch.setattr("database.sqlite_connection.sqlite3.connect",lambda *args,**kwargs:wrapped)
    with pytest.raises(SQLitePragmaPolicyError): open_connection(tmp_path/"closed.db")
    assert wrapped.closed


def test_concurrent_local_connections_share_verified_policy(tmp_path):
    path=tmp_path/"concurrent.db"
    def inspect(_):
        connection=open_connection(path,timeout=5)
        try: return effective_pragmas(connection)
        finally: connection.close()
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(inspect,range(4)))
    assert all(item["journal_mode"]=="wal" and item["foreign_keys"]==1 for item in results)
