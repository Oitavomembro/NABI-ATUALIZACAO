from __future__ import annotations

import json
import sqlite3
from dataclasses import FrozenInstanceError, replace
from datetime import datetime

import pytest

from services.company_profile_service import (
    CompanyActivity, CompanyProfileDraft, CompanyProfileService,
)
from services.security_service import SecurityService


@pytest.fixture
def environment(tmp_path):
    database = tmp_path / "profile.db"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,usuario TEXT,
          modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
        CREATE TABLE log_acesso_admin(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,sucesso INTEGER,detalhes TEXT);
    """)
    connection.commit(); connection.close()
    def connect():
        return sqlite3.connect(database)
    security = SecurityService(connect)
    security.complete_initial_setup(
        username="admin", display_name="Administrador", password="SenhaForte123",
        store_name="Empresa", document="12345678000195",
    )
    assert security.authenticate("admin", "SenhaForte123") is not None
    clock = lambda: datetime(2026, 8, 24, 12, 0, 0)
    return database, connect, security, CompanyProfileService(connect, security_service=security, clock=clock)


def draft(**changes):
    base = CompanyProfileDraft(
        cnpj="12345678000195", legal_name="EMPRESA TESTE LTDA",
        tax_regime="SIMPLES_NACIONAL", business_classification="ME",
        activities=(CompanyActivity("4711302", "Comércio varejista", True),),
        state="BA", city="JUAZEIRO", state_registration="ISENTO",
        municipal_registration="12345", operation_types=("VAREJO",),
        document_types=("NFE", "NFCE"), effective_from="2026-08-01",
        source="DOCUMENTO_CONFIRMADO_PELO_RESPONSAVEL", source_date="2026-08-20",
        confirmed=True,
    )
    return replace(base, **changes)


def test_confirma_versao_imutavel_com_ator_fonte_e_auditoria(environment):
    database, _, _, service = environment
    version = service.confirm(draft(), change_reason="Cadastro inicial confirmado pelo responsável")
    assert version.version == 1 and version.confirmed_by == "admin"
    assert version.source == "DOCUMENTO_CONFIRMADO_PELO_RESPONSAVEL"
    assert version.state_registration == "ISENTO"
    with pytest.raises(FrozenInstanceError):
        version.legal_name = "OUTRO"
    connection = sqlite3.connect(database)
    audit = connection.execute("SELECT modulo,acao,usuario FROM auditoria WHERE modulo='PERFIL_EMPRESARIAL'").fetchone()
    connection.close()
    assert audit == ("PERFIL_EMPRESARIAL", "CONFIRMAR_PERFIL_EMPRESARIAL", "admin")


def test_licenca_fiscal_e_perfil_permanecem_separados(environment):
    database, _, _, service = environment
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO configuracoes VALUES('license.runtime.state','NAO_ALTERAR')")
    connection.execute("INSERT INTO configuracoes VALUES('fiscal.enabled','0')")
    connection.commit(); connection.close()
    service.confirm(draft(), change_reason="Confirmação independente de licença e Fiscal")
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT valor FROM configuracoes WHERE chave='license.runtime.state'").fetchone()[0] == "NAO_ALTERAR"
    assert connection.execute("SELECT valor FROM configuracoes WHERE chave='fiscal.enabled'").fetchone()[0] == "0"
    connection.close()
    readiness = service.readiness()
    assert readiness.informational_only is True and readiness.enables_fiscal is False


def test_sem_sessao_ou_sem_configs_edit_falha_fechado(environment):
    _, _, security, service = environment
    security.logout()
    with pytest.raises(PermissionError):
        service.confirm(draft(), change_reason="Tentativa sem sessão autenticada")
    assert security.authenticate("admin", "SenhaForte123") is not None
    security.save_profile("FISCAL_APENAS", {"fiscal": ["configure"], "configs": ["view"]})
    security.create_user("fiscal", "Fiscal", "SenhaFiscal123", "FISCAL_APENAS")
    security.logout(); assert security.authenticate("fiscal", "SenhaFiscal123") is not None
    assert service.readiness().status == "INCOMPLETO"
    with pytest.raises(PermissionError):
        service.confirm(draft(), change_reason="Fiscal não substitui configuração empresarial")


@pytest.mark.parametrize("change,message", [
    ({"cnpj": "99999999000199"}, "CNPJ"),
    ({"confirmed": False}, "confirmação explícita"),
    ({"source": ""}, "fonte"),
    ({"source_date": "2026-09-01"}, "futuro"),
    ({"activities": (CompanyActivity("123"),)}, "CNAE"),
])
def test_validacao_adversarial_de_fatos_confirmados(environment, change, message):
    _, _, _, service = environment
    with pytest.raises(ValueError, match=message):
        service.confirm(draft(**change), change_reason="Dados submetidos para validação segura")


def test_readiness_expoe_campos_ausentes_sem_inferir_obrigacao(environment):
    _, _, _, service = environment
    incomplete = draft(
        activities=(), state_registration="", municipal_registration="",
        operation_types=(), document_types=(),
    )
    service.confirm(incomplete, change_reason="Perfil parcial confirmado conscientemente")
    readiness = service.readiness()
    assert readiness.status == "INCOMPLETO"
    assert set(readiness.missing_fields) >= {
        "cnaes", "inscricao_estadual", "inscricao_municipal", "tipos_operacao", "tipos_documento",
    }
    assert readiness.enables_fiscal is False


def test_vigencia_futura_fica_agendada_sem_ativacao(environment):
    _, _, _, service = environment
    version = service.confirm(
        draft(effective_from="2026-09-01"),
        change_reason="Alteração empresarial com vigência futura confirmada",
    )
    assert version.version == 1
    assert service.active(on_date="2026-08-24") is None
    assert service.readiness(on_date="2026-08-24").status == "AGENDADO"
    assert service.active(on_date="2026-09-01").version == 1


def test_mudanca_mei_para_me_epp_preserva_intervalos_e_historico(environment):
    _, _, _, service = environment
    first = service.confirm(
        draft(tax_regime="MEI", business_classification="MEI", effective_from="2026-01-01"),
        change_reason="Enquadramento inicial MEI confirmado",
    )
    second = service.confirm(
        draft(tax_regime="SIMPLES_NACIONAL", business_classification="EPP", effective_from="2026-09-01"),
        change_reason="Desenquadramento MEI para EPP confirmado",
        expected_current_version=1,
    )
    history = service.history()
    assert [row.version for row in history] == [1, 2]
    assert history[0].effective_to == "2026-08-31"
    assert first.business_classification == "MEI" and second.business_classification == "EPP"
    assert service.active(on_date="2026-08-01").version == 1
    assert service.active(on_date="2026-09-01").version == 2


def test_concorrencia_otimista_impede_sobrescrita(environment):
    _, _, _, service = environment
    service.confirm(draft(), change_reason="Primeira versão empresarial confirmada")
    with pytest.raises(RuntimeError, match="mudou desde a revisão"):
        service.confirm(
            draft(effective_from="2026-09-01"),
            change_reason="Alteração baseada em versão antiga",
            expected_current_version=0,
        )
    assert len(service.history()) == 1


def test_rollback_cria_nova_versao_sem_apagar_historia(environment):
    _, _, _, service = environment
    service.confirm(draft(effective_from="2026-01-01"), change_reason="Versão empresarial inicial")
    service.confirm(
        draft(legal_name="EMPRESA ALTERADA", effective_from="2026-06-01"),
        change_reason="Mudança societária confirmada", expected_current_version=1,
    )
    restored = service.rollback_to(
        1, effective_from="2026-09-01", reason="Documento anterior voltou a valer",
        expected_current_version=2,
    )
    assert restored.version == 3 and restored.legal_name == "EMPRESA TESTE LTDA"
    assert [row.version for row in service.history()] == [1, 2, 3]


def test_auditoria_ausente_reverte_toda_mutacao(environment):
    database, _, _, service = environment
    connection = sqlite3.connect(database); connection.execute("DROP TABLE auditoria"); connection.commit(); connection.close()
    with pytest.raises(RuntimeError, match="Auditoria indisponível"):
        service.confirm(draft(), change_reason="Esta mudança precisa falhar fechada")
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT 1 FROM configuracoes WHERE chave=?", (service.CONFIG_KEY,)).fetchone() is None
    connection.close()


def test_historico_corrompido_bloqueia_leitura_e_escrita(environment):
    database, _, _, service = environment
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO configuracoes VALUES(?,?)", (service.CONFIG_KEY, "{corrompido"))
    connection.commit(); connection.close()
    with pytest.raises(RuntimeError, match="corrompido"):
        service.readiness()
    with pytest.raises(RuntimeError, match="corrompido"):
        service.confirm(draft(), change_reason="Não sobrescrever histórico corrompido")


def test_cadeia_hash_detecta_adulteracao_estrutural(environment):
    database, _, _, service = environment
    service.confirm(draft(), change_reason="Versão íntegra antes da adulteração")
    connection = sqlite3.connect(database)
    raw = connection.execute("SELECT valor FROM configuracoes WHERE chave=?", (service.CONFIG_KEY,)).fetchone()[0]
    state = json.loads(raw); state["versions"][0]["legal_name"] = "NOME ADULTERADO"
    connection.execute("UPDATE configuracoes SET valor=? WHERE chave=?", (json.dumps(state), service.CONFIG_KEY))
    connection.commit(); connection.close()
    with pytest.raises(RuntimeError, match="Cadeia do histórico"):
        service.history()


def test_migracao_legada_e_apenas_rascunho_sem_persistencia(environment):
    database, _, _, service = environment
    legacy = {
        "cnpj": "12345678000195", "tax_regime": "SIMPLES_NACIONAL", "state": "BA",
        "enabled_models": ["55", "65"],
        "issuer": {"name": "EMPRESA LEGADA", "city": "JUAZEIRO", "state_registration": "ISENTO"},
    }
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO configuracoes VALUES('fiscal.config.v1',?)", (json.dumps(legacy),))
    connection.commit(); connection.close()
    candidate = service.prepare_legacy_migration()
    assert candidate.confirmed is False
    assert candidate.activities == () and candidate.operation_types == ()
    assert candidate.source == "CONFIGURACAO_LEGADA_NABICODE"
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT 1 FROM configuracoes WHERE chave=?", (service.CONFIG_KEY,)).fetchone() is None
    connection.close()
