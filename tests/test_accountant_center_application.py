from __future__ import annotations

from types import SimpleNamespace

import pytest

from commercial.application.accountant_center_dto import AccountantPackagePlan
from commercial.application.accountant_center_service import AccountantCenterApplicationService
from services.accountant_monthly_package_service import AccountantMonthlyPackageService


class Security:
    def __init__(self):
        self.allowed=True; self.session=SimpleNamespace(user=SimpleNamespace(username="contador"))
    def require(self,module,action):
        self.last=(module,action); return self.allowed


class Package:
    def __init__(self):self.calls=[]
    def export(self,**kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(path=kwargs["output_path"],cnpj=kwargs["cnpj"],competence=kwargs["competence"],profile=kwargs["profile"],status="PENDENTE",files=20,movements=7,pendencies=3)
    def normalize_request(self,**kwargs):return AccountantMonthlyPackageService.normalize_request(**kwargs)


def reviewed(application,tmp_path,profile="ESSENCIAL"):
    return application.review(cnpj="12.345.678/0001-95",competence="2026-08",profile=profile,output_path=str(tmp_path/"pacote.zip"),cnpj_confirmed=True)


def test_revisao_e_geracao_revalidam_sessao_e_permissao(tmp_path):
    security=Security(); package=Package(); application=AccountantCenterApplicationService(package,security)
    plan=reviewed(application,tmp_path)
    assert security.last==("relatorios","generate") and plan.reviewed_by=="contador"
    outcome=application.generate(plan)
    assert outcome.movements==7 and len(package.calls)==1
    security.allowed=False
    with pytest.raises(PermissionError):application.generate(plan)
    assert len(package.calls)==1


def test_troca_de_operador_e_plano_adulterado_falham_antes_do_servico(tmp_path):
    security=Security(); package=Package(); application=AccountantCenterApplicationService(package,security); plan=reviewed(application,tmp_path)
    security.session.user.username="outro"
    with pytest.raises(PermissionError,match="sessão mudou"):application.generate(plan)
    security.session.user.username="contador"
    forged=AccountantPackagePlan(plan.cnpj,plan.competence,"AUDITORIA",plan.output_path,plan.reviewed_by,plan.fingerprint)
    with pytest.raises(ValueError,match="alterada"):application.generate(forged)
    assert package.calls==[]


@pytest.mark.parametrize("values,message",[
    ({"cnpj":"123","cnpj_confirmed":True},"CNPJ válido"),
    ({"cnpj":"12345678000195","cnpj_confirmed":False},"Confirme"),
    ({"competence":"08/2026"},"Competência"),
    ({"profile":"OCULTO"},"Perfil inválido"),
    ({"output_path":"pacote.csv"},"arquivo ZIP"),
])
def test_revisao_recusa_entrada_incompleta_sem_exportar(tmp_path,values,message):
    package=Package(); application=AccountantCenterApplicationService(package,Security())
    data={"cnpj":"12345678000195","competence":"2026-08","profile":"ESSENCIAL","output_path":str(tmp_path/"pacote.zip"),"cnpj_confirmed":True}; data.update(values)
    with pytest.raises(ValueError,match=message):application.review(**data)
    assert package.calls==[]


def test_perfis_nao_oferecem_filtro_para_esconder_movimentos(tmp_path):
    application=AccountantCenterApplicationService(Package(),Security())
    assert application.PROFILES==("ESSENCIAL","COMPLETO","AUDITORIA")
    for profile in application.PROFILES: assert reviewed(application,tmp_path,profile).profile==profile
