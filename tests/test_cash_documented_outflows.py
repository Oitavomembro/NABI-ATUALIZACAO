from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest

from commercial.application.cash_application_service import CashApplicationService
from database import DatabaseManager
from database.schema_initializer import initialize_database
from services.cash_service import CashService


@pytest.fixture()
def environment(tmp_path):
    db=DatabaseManager(tmp_path/"cash.db")
    initialize_database(db_name=str(tmp_path/"cash.db"),backup_dir=str(tmp_path/"backups"),pdf_dir=str(tmp_path/"pdfs"),schema_version=20,last_database_update={"executada":False,"de":0,"para":20,"backup":""},network_mode=False,network_role="local",connect=db.connect,read_existing_version=lambda:0,backup_before_update=lambda *_:"")
    cash=CashService(db.connect); cash.open_session("PC1","ANA","100.00",opened_at="24/08/2026 08:00:00")
    return db,cash,tmp_path


def payload(**changes):
    base=dict(outflow_type="DESPESA_EMPRESARIAL",amount="25.50",occurred_on="2026-08-24",competence="2026-08",category="LIMPEZA",payment_method="DINHEIRO",source="CAIXA",beneficiary_id=None,beneficiary_name="",document_type="RECIBO",document_number="R-1",receipt_path="",documentation_pending=True,note="material")
    base.update(changes); return base


def commit(cash,payload_value,key="out:1"):
    normalized=cash.normalize_documented_outflow(payload_value)
    return cash.register_documented_outflow("PC1",normalized,user="ANA",idempotency_key=key,fingerprint=cash.documented_outflow_fingerprint(normalized),occurred_at="24/08/2026 09:00:00")


@pytest.mark.parametrize("kind", sorted(CashService.OUTFLOW_TYPES))
def test_types_are_controlled_and_enter_the_closing(environment,kind):
    db,cash,_=environment; commit(cash,payload(outflow_type=kind),f"out:{kind}")
    state=cash.session_summary(cash.get_open_session("PC1").id)
    assert state["documented_outflows"]==Decimal("25.50")
    assert state["expected_cash"]==Decimal("74.50")


def test_non_cash_outflow_is_visible_but_does_not_change_drawer(environment):
    _,cash,_=environment; commit(cash,payload(payment_method="PIX"),"out:pix")
    state=cash.session_summary(cash.get_open_session("PC1").id)
    assert state["documented_outflows"]==Decimal("25.50")
    assert state["documented_cash_outflows"]==Decimal("0.00")
    assert state["expected_cash"]==Decimal("100.00")


@pytest.mark.parametrize("category", sorted(CashService.OUTFLOW_CATEGORIES))
def test_categories_are_controlled(environment,category):
    _,cash,_=environment; assert commit(cash,payload(category=category),f"cat:{category}")>0


def test_receipt_reference_supplier_and_pending_state(environment):
    db,cash,tmp=environment; receipt=tmp/"receipt.pdf"; receipt.write_bytes(b"%PDF-test")
    with db.session(write=True) as conn:
        supplier=int(conn.execute("INSERT INTO fornecedores(razao_social,nome_fantasia,criado_em,atualizado_em) VALUES('Fornecedor SA','Fornecedor','agora','agora')").lastrowid)
    outflow=commit(cash,payload(outflow_type="PAGAMENTO_FORNECEDOR",category="FORNECEDOR",beneficiary_id=supplier,receipt_path=str(receipt),documentation_pending=False))
    row=db.fetch_one("SELECT beneficiary_name,receipt_path,documentation_pending,accounting_review FROM cash_documented_outflows WHERE id=?",(outflow,))
    assert tuple(row)==("Fornecedor",str(receipt.resolve()),0,"A_REVISAR_PELO_CONTADOR")


def test_idempotency_conflict_and_rollback(environment):
    db,cash,_=environment; first=commit(cash,payload(),"same")
    assert commit(cash,payload(),"same")==first
    normalized=cash.normalize_documented_outflow(payload(amount="30"))
    with pytest.raises(PermissionError): cash.register_documented_outflow("PC1",normalized,user="ANA",idempotency_key="same",fingerprint=cash.documented_outflow_fingerprint(normalized))
    with pytest.raises(ValueError): commit(cash,payload(beneficiary_id=999),"missing")
    assert db.fetch_one("SELECT COUNT(*) FROM cash_outflow_journal WHERE idempotency_key='missing'")[0]==0


def test_concurrent_retry_commits_exactly_once(environment):
    db,cash,_=environment; normalized=cash.normalize_documented_outflow(payload())
    fingerprint=cash.documented_outflow_fingerprint(normalized)
    def execute():
        return cash.register_documented_outflow("PC1",normalized,user="ANA",idempotency_key="concurrent:1",fingerprint=fingerprint)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids=list(pool.map(lambda _index: execute(),range(2)))
    assert ids[0]==ids[1]
    assert db.fetch_one("SELECT COUNT(*) FROM cash_documented_outflows")[0]==1


class Security:
    def __init__(self,allowed=True): self.allowed=allowed; self.session=SimpleNamespace(user=SimpleNamespace(username="ANA"))
    def is_expired(self): return False
    def require(self,module,action): return self.allowed and (module,action)==("financeiro","create")
    def touch(self): pass


def test_application_requires_real_permission_and_immutable_review(environment):
    _,cash,_=environment; denied=CashApplicationService(cash,terminal="PC1",security=Security(False))
    draft=denied.prepare_documented_outflow(**payload())
    with pytest.raises(TypeError): draft.payload["amount"]="99"
    with pytest.raises(PermissionError): denied.confirm_documented_outflow(draft)
    allowed=CashApplicationService(cash,terminal="PC1",security=Security())
    draft=allowed.prepare_documented_outflow(**payload(outflow_type="RETIRADA_SOCIO",category="SALARIOS_PRO_LABORE"))
    assert allowed.confirm_documented_outflow(draft,idempotency_key="owner:1")>0


def test_invalid_data_does_not_persist(environment):
    db,cash,_=environment
    for invalid in (payload(category="DEDUCAO_FISCAL"),payload(amount="0"),payload(receipt_path="C:/inexistente.exe")):
        with pytest.raises(ValueError): cash.normalize_documented_outflow(invalid)
    assert db.fetch_one("SELECT COUNT(*) FROM cash_documented_outflows")[0]==0
