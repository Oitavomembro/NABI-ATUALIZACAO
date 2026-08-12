import logging
from services.admin_audit_service import AdminAuditService


class Connection:
    def __init__(self, table=True): self.table=table; self.executed=[]; self.commits=0; self.closed=False
    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if "sqlite_master" in sql: return Result((1,) if self.table else None)
        return Result(None)
    def commit(self): self.commits += 1
    def rollback(self): pass
    def close(self): self.closed=True

class Result:
    def __init__(self,row): self.row=row
    def fetchone(self): return self.row

class Bus:
    def __init__(self): self.events=[]
    def publish(self, name, **payload): self.events.append((name,payload))


def test_record_event_publishes_and_persists():
    connection=Connection(); bus=Bus()
    service=AdminAuditService(lambda: connection, logging.getLogger("test"))
    service.record_event("TESTE", "SALVAR", object_id=7, details="ok", event_bus=bus)
    assert bus.events[0][0] == "auditoria.registrada"
    assert connection.commits == 1
    assert connection.closed is True
    assert any("INSERT INTO auditoria" in sql for sql, _ in connection.executed)


def test_record_event_skips_database_when_missing():
    called=[]
    service=AdminAuditService(lambda: called.append(True), logging.getLogger("test"))
    service.record_event("TESTE", "LER", database_exists=False)
    assert called == []
