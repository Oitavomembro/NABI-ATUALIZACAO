from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from administration.nfe_purchase_import_service import NFePurchaseImportManagementService
from database import DatabaseManager


class Security:
    def __init__(self, user="operador", allowed=True):
        self.session = SimpleNamespace(user=SimpleNamespace(username=user))
        self.allowed = allowed
    def is_expired(self): return False
    def require(self, _module, _action): return self.allowed
    def touch(self): pass


def service(tmp_path, *, user="operador", company="12345678000199"):
    database = DatabaseManager(tmp_path / "drafts.db")
    repository = SimpleNamespace(database=database)
    imports = SimpleNamespace(repository=repository)
    result = NFePurchaseImportManagementService(
        imports, Security(user), company_document_provider=lambda: company,
    )
    return result, database


def sample(tmp_path):
    source = tmp_path / "nota.xml"; source.write_bytes(b"<nfe>evidencia</nfe>")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    draft = SimpleNamespace(
        access_key="1" * 44, source_sha256=digest, source_path=str(source),
        number="77", supplier_name="Fornecedor", supplier_document="11222333000144",
        items=(SimpleNamespace(),),
    )
    rows = ({"acao":"CRIAR","produto_id":None,"codigo":"A","descricao":"Nome editado",
             "codigo_barras":"789","tipo_fator":"DIVIDIR","fator":"2","unidade":"UN",
             "margem":"30.5","preco":"13.05","status":"NOVO"},)
    return draft, rows


def test_checkpoint_reinicia_e_reabre_exatamente_por_usuario_empresa_hash(tmp_path, monkeypatch):
    app, _database = service(tmp_path); draft, rows = sample(tmp_path)
    draft_id = app.save_draft(draft, rows, page=2)
    restarted, _ = service(tmp_path)
    monkeypatch.setattr(restarted, "prepare", lambda _path: draft)
    resumed, state = restarted.resume_draft(draft_id)
    assert resumed is draft
    assert state == {"version":1,"page":2,"rows":[rows[0]]}
    assert restarted.pending_drafts()[0]["id"] == draft_id


def test_outro_usuario_empresa_ou_sem_permissao_nao_enxerga_rascunho(tmp_path):
    owner, _ = service(tmp_path); draft, rows = sample(tmp_path)
    draft_id = owner.save_draft(draft, rows)
    other, _ = service(tmp_path, user="outro")
    assert other.pending_drafts() == ()
    with pytest.raises(PermissionError): other.resume_draft(draft_id)
    company, _ = service(tmp_path, company="99999999000199")
    assert company.pending_drafts() == ()


def test_corrupcao_e_xml_alterado_falham_fechado_e_preservam(tmp_path, monkeypatch):
    app, database = service(tmp_path); draft, rows = sample(tmp_path)
    draft_id = app.save_draft(draft, rows)
    database.execute("UPDATE nfe_importacao_rascunhos SET estado_json='{}' WHERE id=?",(draft_id,))
    with pytest.raises(ValueError, match="corrompido"): app.resume_draft(draft_id)
    assert app.pending_drafts()[0]["id"] == draft_id
    app.save_draft(draft, rows); Path(draft.source_path).write_bytes(b"alterado")
    with pytest.raises(ValueError, match="alterado"): app.resume_draft(draft_id)
    assert app.pending_drafts()[0]["id"] == draft_id


def test_descarte_exige_confirmacao_mantem_auditoria_e_e_idempotente_no_salvamento(tmp_path):
    app, database = service(tmp_path); draft, rows = sample(tmp_path)
    first = app.save_draft(draft, rows); second = app.save_draft(draft, rows, page=1)
    assert first == second
    with pytest.raises(PermissionError): app.discard_draft(first)
    app.discard_draft(first, confirmed=True)
    assert app.pending_drafts() == ()
    audit = database.fetch_all("SELECT evento FROM nfe_importacao_rascunho_auditoria WHERE rascunho_id=? ORDER BY id",(first,))
    assert [row["evento"] for row in audit] == ["CRIADO", "DESCARTADO"]


def test_falha_final_preserva_e_sucesso_atomico_conclui(tmp_path, monkeypatch):
    app, database = service(tmp_path); draft, _rows = sample(tmp_path)
    draft.protocol_status_evidence = "100"; draft.fingerprint = "review"
    document = SimpleNamespace(itens=(SimpleNamespace(
        quantidade="2", valor_unitario="10", codigo="A", descricao="Produto",
        codigo_barras="789", ncm="", cest="",
    ),))
    rows = ({"acao":"CRIAR","produto_id":None,"codigo":"A","descricao":"Produto",
             "codigo_barras":"789","tipo_fator":"MULTIPLICAR","fator":"1","unidade":"UN",
             "margem":"30","preco":"13","status":"NOVO"},)
    saved_id = app.save_draft(draft, rows)
    monkeypatch.setattr(app, "document", lambda _id: document)
    monkeypatch.setattr(app, "units", lambda: (("UN","Unidade"),))
    app.imports.validar_decisao = lambda *_args: None
    app.imports.importar_atomicamente = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("queda final"))
    draft.draft_id = "runtime"
    with pytest.raises(RuntimeError, match="queda final"):
        app.commit(draft, rows, confirmed=True)
    assert app.pending_drafts()[0]["id"] == saved_id
    app.imports.importar_atomicamente = lambda *_args, **_kwargs: {"importacao_id": 9}
    assert app.commit(draft, rows, confirmed=True)["importacao_id"] == 9
    assert app.pending_drafts() == ()
    row = database.fetch_one("SELECT status FROM nfe_importacao_rascunhos WHERE id=?",(saved_id,))
    assert row["status"] == "CONCLUIDO"
