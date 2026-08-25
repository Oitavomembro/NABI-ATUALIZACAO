from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from commercial.application.cash_application_service import CashApplicationService
from services.cash_service import CashService


SCHEMA = """
CREATE TABLE cash_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,terminal TEXT NOT NULL,opened_by TEXT NOT NULL,opened_at TEXT NOT NULL,opening_balance TEXT NOT NULL,opening_mode TEXT NOT NULL,status TEXT NOT NULL,closed_by TEXT DEFAULT '',closed_at TEXT DEFAULT '',expected_cash TEXT,counted_cash TEXT,difference TEXT,closing_note TEXT DEFAULT '');
CREATE UNIQUE INDEX one_open_cash ON cash_sessions(terminal) WHERE status='ABERTO';
CREATE TABLE cash_closing_journal(cash_session_id INTEGER PRIMARY KEY,fingerprint TEXT NOT NULL,status TEXT NOT NULL,result_json TEXT NOT NULL DEFAULT '',username TEXT NOT NULL,created_at TEXT NOT NULL,committed_at TEXT NOT NULL DEFAULT '');
CREATE TABLE cash_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,cash_session_id INTEGER NOT NULL,type TEXT NOT NULL,amount TEXT NOT NULL,user_id TEXT NOT NULL,note TEXT DEFAULT '',created_at TEXT NOT NULL);
CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,tipo TEXT,forma_pagamento TEXT,valor REAL,valor_decimal TEXT,data TEXT,status_pagamento TEXT DEFAULT 'PAGO');
CREATE TABLE auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,usuario TEXT,modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
"""


class Security:
    def __init__(self, *, allowed=True, expired=False, username="ANA"):
        self.allowed = allowed
        self.expired = expired
        self.touches = 0
        self.session = SimpleNamespace(user=SimpleNamespace(username=username))

    def is_expired(self):
        return self.expired

    def require(self, module, action):
        return self.allowed and (module, action) == ("financeiro", "view")

    def touch(self):
        self.touches += 1


@pytest.fixture
def cash(tmp_path):
    path = tmp_path / "cash.db"
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.close()
    service = CashService(lambda: sqlite3.connect(path, timeout=5))
    service.open_session(
        "PC-1", "ABERTURA", "100.00", opened_at="24/08/2026 08:00:00"
    )
    return path, service


def counts(path):
    with sqlite3.connect(path) as connection:
        session = connection.execute(
            "SELECT status,closed_by,expected_cash,counted_cash,difference FROM cash_sessions"
        ).fetchone()
        journal = connection.execute("SELECT COUNT(*) FROM cash_closing_journal").fetchone()[0]
        audits = connection.execute(
            "SELECT COUNT(*) FROM auditoria WHERE acao='CAIXA_FECHADO'"
        ).fetchone()[0]
    return session, journal, audits


def test_fechamento_unico_e_repeticao_identica_reusam_resultado(cash):
    path, service = cash
    first = service.close_session(
        "PC-1", "100.00", "ANA", closed_at="24/08/2026 18:00:00"
    )
    repeated = service.close_session(
        "PC-1", "100.00", "ANA", closed_at="24/08/2026 18:05:00"
    )
    assert repeated == first
    assert counts(path) == (("FECHADO", "ANA", "100", "100.00", "0.00"), 1, 1)


def test_saldo_oficial_e_calculado_dentro_do_fechamento(cash):
    path, service = cash
    with sqlite3.connect(path) as connection:
        connection.execute(
            """INSERT INTO movimentacoes(tipo,forma_pagamento,valor,valor_decimal,data)
               VALUES('COMPRA','DINHEIRO R$ 30.00 + PIX R$ 20.00',50,'50.00','24/08/2026 09:00:00')"""
        )
        connection.execute(
            """INSERT INTO movimentacoes(tipo,forma_pagamento,valor,valor_decimal,data)
               VALUES('PAGAMENTO','DINHEIRO',10,'10.00','24/08/2026 10:00:00')"""
        )
        connection.commit()
    service.register_session_movement(
        "PC-1", "SUPRIMENTO", 5, "ANA", "troco", "24/08/2026 11:00:00"
    )
    service.register_session_movement(
        "PC-1", "SANGRIA", 2, "ANA", "cofre", "24/08/2026 12:00:00"
    )
    closed = service.close_session(
        "PC-1", 143, "ANA", closed_at="24/08/2026 18:00:00"
    )
    assert closed.expected_cash == 143
    assert closed.difference == 0
    assert counts(path)[1:] == (1, 1)


def test_repeticao_divergente_falha_fechada_sem_alterar_oficial(cash):
    path, service = cash
    service.close_session("PC-1", 100, "ANA", closed_at="24/08/2026 18:00:00")
    with pytest.raises(ValueError, match="diverge"):
        service.close_session("PC-1", 99, "ANA", "falta", "24/08/2026 18:01:00")
    assert counts(path) == (("FECHADO", "ANA", "100", "100.00", "0.00"), 1, 1)


def test_caixa_inexistente_e_fechado_sem_journal_sao_bloqueados(cash):
    path, service = cash
    with pytest.raises(RuntimeError, match="Não existe caixa"):
        service.close_session("OUTRO", 0, "ANA")
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE cash_sessions SET status='FECHADO'")
        connection.commit()
    with pytest.raises(RuntimeError, match="já foi fechada"):
        service.close_session("PC-1", 100, "ANA")


@pytest.mark.parametrize("failure", ["audit", "journal"])
def test_falha_de_auditoria_ou_journal_reverte_tudo(cash, monkeypatch, failure):
    path, service = cash
    if failure == "audit":
        monkeypatch.setattr(
            service, "_audit", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit fail"))
        )
    else:
        with sqlite3.connect(path) as connection:
            connection.execute(
                """CREATE TRIGGER fail_cash_journal BEFORE UPDATE OF status ON cash_closing_journal
                   WHEN NEW.status='COMMITTED' BEGIN SELECT RAISE(ABORT,'journal fail'); END"""
            )
            connection.commit()
    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        service.close_session("PC-1", 100, "ANA", closed_at="24/08/2026 18:00:00")
    assert counts(path) == (("ABERTO", "", None, None, None), 0, 0)


def test_ausencia_da_auditoria_obrigatoria_reverte_fechamento(cash):
    path, service = cash
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE auditoria")
        connection.commit()
    with pytest.raises(RuntimeError, match="Auditoria obrigatória"):
        service.close_session("PC-1", 100, "ANA")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT status FROM cash_sessions").fetchone()[0] == "ABERTO"
        assert connection.execute("SELECT COUNT(*) FROM cash_closing_journal").fetchone()[0] == 0


def test_concorrencia_identica_fecha_uma_vez(cash):
    path, service = cash

    def close():
        return service.close_session(
            "PC-1", 100, "ANA", closed_at="24/08/2026 18:00:00"
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: close(), range(2)))
    assert results[0] == results[1]
    assert counts(path)[1:] == (1, 1)


@pytest.mark.parametrize(
    "security",
    [Security(allowed=False), Security(expired=True), Security(username="")],
)
def test_porta_manual_exige_sessao_ator_e_permissao_reais(cash, security):
    path, service = cash
    application = CashApplicationService(
        service, terminal="PC-1", user="texto-nao-confiavel", security=security
    )
    with pytest.raises(PermissionError):
        application.close(100)
    assert counts(path) == (("ABERTO", "", None, None, None), 0, 0)


def test_porta_manual_usa_ator_da_sessao(cash):
    path, service = cash
    security = Security(username="OPERADOR_REAL")
    application = CashApplicationService(
        service, terminal="PC-1", user="texto-antigo", security=security
    )
    closed = application.close(100)
    assert closed.closed_by == "OPERADOR_REAL"
    assert security.touches == 1
    assert counts(path)[1:] == (1, 1)
