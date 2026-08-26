import sqlite3
from decimal import Decimal

import pytest

from assistant_nabi.cash_drafts import CashDraftService
from assistant_nabi.cash_gateway import NabiCodeCashAssistantGateway
from assistant_nabi.confirmations import DraftConfirmationService
from assistant_nabi.contracts import AssistantActor, CapabilityLevel
from commercial.application.cash_application_service import CashApplicationService
from services.cash_service import CashService


def database(tmp_path):
    path = tmp_path / "cash.db"
    connection = sqlite3.connect(path)
    connection.executescript("""
      CREATE TABLE cash_sessions(id INTEGER PRIMARY KEY,terminal TEXT,opened_by TEXT,
        opened_at TEXT,opening_balance TEXT,opening_mode TEXT,status TEXT,
        closed_by TEXT,closed_at TEXT,expected_cash TEXT,counted_cash TEXT,
        difference TEXT,closing_note TEXT);
      CREATE TABLE cash_movements(id INTEGER PRIMARY KEY,cash_session_id INTEGER,type TEXT,
        amount TEXT,user_id TEXT,note TEXT,created_at TEXT);
      CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY,tipo TEXT,forma_pagamento TEXT,
        valor REAL,valor_decimal TEXT,data TEXT,status_pagamento TEXT,
        responsavel TEXT,descricao TEXT);
      CREATE TABLE assistant_operation_journal(id INTEGER PRIMARY KEY,
        idempotency_key TEXT UNIQUE,operation_kind TEXT,fingerprint TEXT,status TEXT,
        result_json TEXT,username TEXT,created_at TEXT,committed_at TEXT);
      CREATE TABLE auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,
        usuario TEXT,modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
    """)
    connection.commit(); connection.close()
    return lambda: sqlite3.connect(path), path


def confirmed(draft):
    actor = AssistantActor("maria", "GERENTE", "sessao-1")
    broker = DraftConfirmationService()
    challenge = broker.issue(draft, actor=actor)
    assert challenge.required_capability is CapabilityLevel.REINFORCED_CONFIRMATION
    return broker.confirm(token=challenge.token, draft=draft, actor=actor)


def test_abertura_e_movimentos_sao_atomicos_e_idempotentes(tmp_path):
    factory, path = database(tmp_path)
    app = CashApplicationService(CashService(factory), terminal="CX-1", user="maria")
    drafts = CashDraftService(app); gateway = NabiCodeCashAssistantGateway(app)
    opening = drafts.prepare_open(opening_balance="100.00")
    first = gateway.execute(opening, confirmed(opening))
    replay = app.open_assisted(
        opening.amount, opening.opening_mode, username="maria",
        idempotency_key=f"nabi:cash:{opening.draft_id}",
        operation_fingerprint=opening.fingerprint,
    )
    assert first["session_id"] == replay["session_id"]
    assert replay["idempotent_replay"] is True
    supply = drafts.prepare_movement(movement_type="SUPRIMENTO", amount="25", note="troco")
    gateway.execute(supply, confirmed(supply))
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cash_sessions").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM cash_movements").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM assistant_operation_journal WHERE status='COMMITTED'").fetchone()[0] == 2


def test_fingerprint_divergente_nao_duplica_movimento(tmp_path):
    factory, path = database(tmp_path)
    service = CashService(factory)
    service.open_session_assisted("CX", "maria", 0, "VALOR_INFORMADO",
                                  idempotency_key="open", operation_fingerprint="a" * 64)
    service.register_session_movement_assisted(
        "CX", "SANGRIA", 10, "maria", "teste",
        idempotency_key="movement", operation_fingerprint="b" * 64,
    )
    with pytest.raises(PermissionError, match="outro conteúdo"):
        service.register_session_movement_assisted(
            "CX", "SANGRIA", 10, "maria", "teste",
            idempotency_key="movement", operation_fingerprint="c" * 64,
        )
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cash_movements").fetchone()[0] == 1


def test_chave_de_outra_operacao_nao_reutiliza_resultado(tmp_path):
    factory, path = database(tmp_path)
    service = CashService(factory)
    service.open_session_assisted(
        "CX", "maria", 0, "VALOR_INFORMADO",
        idempotency_key="shared", operation_fingerprint="a" * 64,
    )
    with pytest.raises(PermissionError, match="outra operação"):
        service.register_session_movement_assisted(
            "CX", "SUPRIMENTO", 10, "maria", "teste",
            idempotency_key="shared", operation_fingerprint="a" * 64,
        )
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cash_movements").fetchone()[0] == 0


def test_fechamento_assistido_fica_bloqueado_sem_atomicidade(tmp_path):
    factory, _path = database(tmp_path)
    app = CashApplicationService(CashService(factory), terminal="CX", user="maria")
    app.open_assisted(Decimal("0"), "VALOR_INFORMADO", username="maria",
                      idempotency_key="open", operation_fingerprint="a" * 64)
    draft = CashDraftService(app).prepare_close(counted_cash="0")
    with pytest.raises(RuntimeError, match="permanece bloqueado"):
        NabiCodeCashAssistantGateway(app).execute(draft, confirmed(draft))
    assert app.current().is_open


def test_autorizacao_e_operador_reais_sao_obrigatorios(tmp_path):
    factory, _path = database(tmp_path)
    app = CashApplicationService(CashService(factory), terminal="CX", user="maria")
    draft = CashDraftService(app).prepare_open()
    with pytest.raises(PermissionError, match="broker"):
        NabiCodeCashAssistantGateway(app).execute(draft, object())
    with pytest.raises(PermissionError, match="não corresponde"):
        app.open_assisted(0, "VALOR_INFORMADO", username="forjado",
                          idempotency_key="x", operation_fingerprint="a" * 64)
