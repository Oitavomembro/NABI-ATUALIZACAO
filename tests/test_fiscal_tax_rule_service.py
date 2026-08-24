import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
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
;
CREATE TABLE fiscal_tax_rule_revisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,rule_id INTEGER NOT NULL,
 revision_number INTEGER NOT NULL,event_kind TEXT NOT NULL,payload_json TEXT NOT NULL,
 previous_hash TEXT NOT NULL DEFAULT '',current_hash TEXT NOT NULL,actor TEXT NOT NULL,
 change_reason TEXT NOT NULL DEFAULT '',recorded_at TEXT NOT NULL,
 UNIQUE(rule_id,revision_number)
);
CREATE TRIGGER trg_fiscal_tax_rule_revisions_no_update
BEFORE UPDATE ON fiscal_tax_rule_revisions BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER trg_fiscal_tax_rule_revisions_no_delete
BEFORE DELETE ON fiscal_tax_rule_revisions BEGIN SELECT RAISE(ABORT, 'append-only'); END
"""


@pytest.fixture
def service():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "rules.db"
        connection = sqlite3.connect(path)
        connection.executescript(SCHEMA)
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
    with pytest.raises(ValueError, match="somente regras tributárias de venda"):
        service.save(rule(operation_kind="DEVOLUCAO"))


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
    assert service.resolve(
        tax_regime="SIMPLES_NACIONAL", ncm="94036000", destination_state="SE",
        operation_kind="DEVOLUCAO",
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


def test_cadastro_recusa_conflito_ativo_de_mesma_precedencia(service):
    existing = service.save(rule())

    with pytest.raises(ValueError, match=rf"Conflito auditável.*IDs: {existing.id}"):
        service.save(rule(name="Duplicada com conteúdo tributário diferente", icms_code="103"))

    assert [item.id for item in service.list_rules()] == [existing.id]


def test_cadastro_recusa_cest_especifico_sobre_regra_generica_de_mesma_precedencia(service):
    existing = service.save(rule())

    with pytest.raises(ValueError, match=rf"Conflito auditável.*IDs: {existing.id}"):
        service.save(rule(name="CEST concorrente", cest="1234567"))


def test_resolucao_de_dados_antigos_ambiguos_falha_fechado_sem_usar_id_desc(service):
    first = service.save(rule(name="Primeira regra"))
    connection = service.connection_factory()
    try:
        values = rule(name="Regra antiga concorrente", icms_code="103")
        normalized = service.normalize(values)
        columns = tuple(normalized)
        cursor = connection.execute(
            f"INSERT INTO fiscal_tax_rules ({','.join(columns)},created_at,updated_at) "
            f"VALUES ({','.join('?' for _ in columns)},'2026-08-20','2026-08-20')",
            tuple(normalized[column] for column in columns),
        )
        second_id = int(cursor.lastrowid)
        connection.commit()
    finally:
        connection.close()

    assert second_id > first.id
    with pytest.raises(
        ValueError,
        match=rf"Conflito auditável.*IDs: {first.id}, {second_id}",
    ):
        service.resolve(
            tax_regime="SIMPLES_NACIONAL", ncm="94036000", destination_state="BA"
        )


def test_historico_tecnico_encadeia_create_update_e_deactivate_sem_mudar_api(service):
    saved = service.save(rule(), actor="operador", change_reason="cadastro aprovado")
    updated = service.save(
        rule(name="Venda regular revisada"), rule_id=saved.id,
        actor="gerente", change_reason="revisão técnica",
    )
    service.deactivate(updated.id)

    assert updated.id == saved.id
    revisions = service.list_revisions(saved.id)
    assert [item["event_kind"] for item in revisions] == ["CREATED", "UPDATED", "DEACTIVATED"]
    assert [item["revision_number"] for item in revisions] == [1, 2, 3]
    assert revisions[0]["actor"] == "operador"
    assert revisions[1]["previous_hash"] == revisions[0]["current_hash"]
    assert service.verify_revision_chain(saved.id) == {
        "valid": True, "rule_id": saved.id, "revision_count": 3,
    }


def test_actor_ausente_e_registrado_sem_inventar_identidade(service):
    saved = service.save(rule())
    assert service.list_revisions(saved.id)[0]["actor"] == "NAO_INFORMADO"


def test_historico_e_append_only_e_adulteracao_e_detectada(service):
    saved = service.save(rule())
    connection = service.connection_factory()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE fiscal_tax_rule_revisions SET actor='forjado' WHERE rule_id=?",
                (saved.id,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM fiscal_tax_rule_revisions WHERE rule_id=?", (saved.id,)
            )
        connection.rollback()
        connection.execute("DROP TRIGGER trg_fiscal_tax_rule_revisions_no_update")
        connection.execute(
            "UPDATE fiscal_tax_rule_revisions SET payload_json='{}' WHERE rule_id=?",
            (saved.id,),
        )
        connection.commit()
    finally:
        connection.close()
    assert service.verify_revision_chain(saved.id)["valid"] is False


def test_falha_do_journal_reverte_a_regra_na_mesma_transacao(service):
    connection = service.connection_factory()
    try:
        connection.execute("""
            CREATE TRIGGER reject_revision BEFORE INSERT ON fiscal_tax_rule_revisions
            BEGIN SELECT RAISE(ABORT, 'falha simulada no journal'); END
        """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.IntegrityError, match="falha simulada"):
        service.save(rule())
    assert service.list_rules(include_inactive=True) == []


def test_updates_concorrentes_serializam_numeros_de_revisao(service):
    saved = service.save(rule())

    def update(name):
        return service.save(rule(name=name), rule_id=saved.id).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(update, ("Revisão A", "Revisão B"))) == [saved.id, saved.id]

    revisions = service.list_revisions(saved.id)
    assert [item["revision_number"] for item in revisions] == [1, 2, 3]
    assert service.verify_revision_chain(saved.id)["valid"] is True
