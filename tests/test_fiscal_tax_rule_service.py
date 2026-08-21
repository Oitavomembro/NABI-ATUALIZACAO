import sqlite3
import tempfile
from pathlib import Path

import pytest

from services.fiscal_tax_rule_service import FiscalTaxRuleService


SCHEMA = """
CREATE TABLE fiscal_tax_rules (
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,active INTEGER NOT NULL,
 issuer_state TEXT NOT NULL,destination_state TEXT NOT NULL,tax_regime TEXT NOT NULL,
 ncm_prefix TEXT NOT NULL,cest TEXT NOT NULL,operation_kind TEXT NOT NULL,
 icms_code TEXT NOT NULL,icms_rate TEXT NOT NULL,icms_base_reduction TEXT NOT NULL,sn_credit_rate TEXT NOT NULL,
 st_mva TEXT NOT NULL,st_rate TEXT NOT NULL,fcp_st_rate TEXT NOT NULL,
 difal_internal_rate TEXT NOT NULL,difal_interstate_rate TEXT NOT NULL,
 difal_fcp_rate TEXT NOT NULL,benefit_code TEXT NOT NULL,approved_by TEXT NOT NULL,
 approved_at TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
)
"""


@pytest.fixture
def service():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "rules.db"
        connection = sqlite3.connect(path)
        connection.execute(SCHEMA)
        connection.commit()
        connection.close()
        yield FiscalTaxRuleService(lambda: sqlite3.connect(path))


def rule(**changes):
    values = {
        "name": "Venda regular móveis", "issuer_state": "BA",
        "destination_state": "*", "tax_regime": "SIMPLES_NACIONAL",
        "ncm_prefix": "9403", "cest": "", "operation_kind": "VENDA",
        "icms_code": "102", "icms_rate": "0", "icms_base_reduction": "0", "sn_credit_rate": "0",
        "st_mva": "0", "st_rate": "0", "fcp_st_rate": "0",
        "difal_internal_rate": "0", "difal_interstate_rate": "0",
        "difal_fcp_rate": "0", "benefit_code": "",
        "approved_by": "CONTADOR TESTE", "approved_at": "2026-08-20",
    }
    values.update(changes)
    return values


def test_regra_exige_aprovacao_contabil_e_nao_aceita_outra_uf_emitente(service):
    with pytest.raises(ValueError, match="responsável"):
        service.save(rule(approved_by=""))
    with pytest.raises(ValueError, match="somente para a Bahia"):
        service.save(rule(issuer_state="SP"))


def test_icms_st_exige_cest_e_taxas_nao_podem_ser_inventadas(service):
    with pytest.raises(ValueError, match="CEST"):
        service.save(rule(icms_code="201", st_mva="40"))
    with pytest.raises(ValueError, match="entre 0 e 100"):
        service.save(rule(icms_rate="101"))


def test_codigo_de_beneficio_respeita_formato_do_schema_oficial(service):
    saved = service.save(rule(benefit_code="BA123456"))
    assert saved.benefit_code == "BA123456"
    with pytest.raises(ValueError, match="8 ou 10 caracteres"):
        service.save(rule(benefit_code="BA 123"))


def test_resolucao_prefere_ncm_e_uf_mais_especificos(service):
    generic = service.save(rule())
    specific = service.save(rule(
        name="Regra específica BA para SE", destination_state="SE",
        ncm_prefix="940360", icms_code="102",
    ))

    assert service.resolve(
        tax_regime="SIMPLES_NACIONAL", ncm="94036000", destination_state="SE"
    ).id == specific.id
    assert service.resolve(
        tax_regime="SIMPLES_NACIONAL", ncm="94032000", destination_state="MG"
    ).id == generic.id
    assert service.resolve(
        tax_regime="LUCRO_REAL", ncm="94036000", destination_state="SE"
    ) is None


def test_desativacao_preserva_historico_e_remove_regra_da_resolucao(service):
    saved = service.save(rule())
    assert [item.id for item in service.list_rules()] == [saved.id]

    service.deactivate(saved.id)

    assert service.list_rules() == []
    assert [item.id for item in service.list_rules(include_inactive=True)] == [saved.id]
    assert service.resolve(
        tax_regime="SIMPLES_NACIONAL", ncm="94036000", destination_state="BA"
    ) is None
