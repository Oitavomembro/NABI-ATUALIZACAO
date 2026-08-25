from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from commercial.application.accountant_center_dto import AccountantPackagePlan
from commercial.application.accountant_center_service import (
    AccountantCenterApplicationService,
    CompanyIdentity,
)
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
        Path(kwargs["output_path"]).write_bytes(b"pacote-contabil")
        return SimpleNamespace(path=kwargs["output_path"],cnpj=kwargs["cnpj"],competence=kwargs["competence"],profile=kwargs["profile"],status="PENDENTE",files=20,movements=7,pendencies=3)
    def normalize_request(self,**kwargs):return AccountantMonthlyPackageService.normalize_request(**kwargs)


def identity():
    return CompanyIdentity("12.345.678/0001-95", "EMPRESA TESTE LTDA", "cadastro central")


def application(package=None, security=None, provider=identity):
    return AccountantCenterApplicationService(package or Package(), security or Security(), provider)


def reviewed(application,tmp_path,profile="ESSENCIAL"):
    return application.review(competence="2026-08",profile=profile,output_path=str(tmp_path/"pacote.zip"))


def test_revisao_e_geracao_revalidam_sessao_e_permissao(tmp_path):
    security=Security(); package=Package(); app=application(package,security)
    plan=reviewed(app,tmp_path)
    assert security.last==("relatorios","generate") and plan.reviewed_by=="contador"
    outcome=app.generate(plan)
    assert outcome.movements==7 and len(package.calls)==1
    security.allowed=False
    with pytest.raises(PermissionError):app.generate(plan)
    assert len(package.calls)==1


def test_troca_de_operador_e_plano_adulterado_falham_antes_do_servico(tmp_path):
    security=Security(); package=Package(); app=application(package,security); plan=reviewed(app,tmp_path)
    security.session.user.username="outro"
    with pytest.raises(PermissionError,match="sessão mudou"):app.generate(plan)
    security.session.user.username="contador"
    forged=AccountantPackagePlan(plan.cnpj,plan.competence,"AUDITORIA",plan.output_path,plan.reviewed_by,plan.fingerprint)
    with pytest.raises(ValueError,match="alterada"):app.generate(forged)
    assert package.calls==[]


@pytest.mark.parametrize("values,message",[
    ({"competence":"08/2026"},"Competência"),
    ({"profile":"OCULTO"},"Perfil inválido"),
    ({"output_path":"pacote.csv"},"arquivo ZIP"),
])
def test_revisao_recusa_entrada_incompleta_sem_exportar(tmp_path,values,message):
    package=Package(); app=application(package)
    data={"competence":"2026-08","profile":"ESSENCIAL","output_path":str(tmp_path/"pacote.zip")}; data.update(values)
    with pytest.raises(ValueError,match=message):app.review(**data)
    assert package.calls==[]


def test_perfis_nao_oferecem_filtro_para_esconder_movimentos(tmp_path):
    app=application()
    assert app.PROFILES==("ESSENCIAL","COMPLETO","AUDITORIA")
    for profile in app.PROFILES: assert reviewed(app,tmp_path,profile).profile==profile


def test_identidade_central_e_obrigatoria_e_cnpj_nao_e_entrada_manual(tmp_path):
    package=Package(); app=application(package)
    plan=reviewed(app,tmp_path)
    assert plan.cnpj=="12345678000195"
    assert "cnpj" not in AccountantCenterApplicationService.review.__annotations__
    with pytest.raises(TypeError):
        app.review(cnpj="99999999000199",competence="2026-08",profile="ESSENCIAL",output_path=str(tmp_path/"x.zip"))


@pytest.mark.parametrize("provider,message", [
    (lambda: CompanyIdentity("12345678000195", "EMPRESA", ""), "origem"),
    (lambda: (_ for _ in ()).throw(RuntimeError("CNPJ divergente entre fontes")), "divergente"),
])
def test_fonte_ausente_ou_divergente_bloqueia_antes_de_exportar(tmp_path,provider,message):
    package=Package(); app=application(package,provider=provider)
    with pytest.raises(RuntimeError,match=message): reviewed(app,tmp_path)
    assert package.calls==[]
