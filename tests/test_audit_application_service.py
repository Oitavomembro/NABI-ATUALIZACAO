from types import SimpleNamespace

import pytest

from administration.audit_application_service import AuditApplicationService


class Security:
    def __init__(self, allowed=True):
        self.allowed=allowed; self.session=SimpleNamespace(user=SimpleNamespace(username="admin")); self.touches=0
    def is_expired(self): return False
    def require(self,module,action): return self.allowed and (module,action)==("technical","audit")
    def touch(self): self.touches+=1


class Audit:
    def __init__(self): self.limits=[]
    def list_security_audit(self,limit): self.limits.append(limit); return [SimpleNamespace(date="24/08/2026",user="admin",action="LOGIN",result="SUCESSO",details="Acesso")]


def test_consulta_exige_permissao_e_limita_quinhentos():
    audit=Audit(); security=Security(); application=AuditApplicationService(audit,security)
    page=application.load(limit=9999)
    assert page.limit==500 and audit.limits==[500] and page.entries[0].user=="admin"
    assert security.touches==1


def test_sem_permissao_falha_antes_de_consultar():
    audit=Audit(); application=AuditApplicationService(audit,Security(False))
    with pytest.raises(PermissionError): application.load()
    assert audit.limits==[]


def test_sem_sessao_falha_fechado():
    security=Security(); security.session=None; audit=Audit()
    with pytest.raises(PermissionError): AuditApplicationService(audit,security).load()
    assert audit.limits==[]
