from __future__ import annotations

import sqlite3

from repositories.financeiro_repository import FinanceiroRepository


class DatabaseFake:
    def __init__(self, connection):
        self.connection = connection

    def fetch_one(self, sql, params=()):
        return self.connection.execute(sql, params).fetchone()


def criar_repositorio():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE pagamentos_titulos (id INTEGER PRIMARY KEY);
        CREATE TABLE auditoria (
            data TEXT, usuario TEXT, modulo TEXT, acao TEXT,
            objeto TEXT, detalhes TEXT, resultado TEXT
        );
        """
    )
    return FinanceiroRepository(DatabaseFake(connection)), connection


def test_configuracao_json_preserva_unicode_e_ordena_chaves():
    repo, conn = criar_repositorio()
    repo.salvar_configuracao_json("financeiro_teste", {"z": 1, "ação": "ok"}, conn)
    bruto = conn.execute("SELECT valor FROM configuracoes WHERE chave='financeiro_teste'").fetchone()[0]
    assert bruto == '{"ação": "ok", "z": 1}'
    assert repo.obter_configuracao_json("financeiro_teste", conn) == {"ação": "ok", "z": 1}


def test_configuracao_json_invalida_retorna_dicionario_vazio():
    repo, conn = criar_repositorio()
    conn.execute("INSERT INTO configuracoes(chave,valor) VALUES('x','não-json')")
    assert repo.obter_configuracao_json("x", conn) == {}


def test_pagamento_existe_e_auditoria_financeira():
    repo, conn = criar_repositorio()
    conn.execute("INSERT INTO pagamentos_titulos(id) VALUES(7)")
    assert repo.pagamento_existe(7, conn) is True
    assert repo.pagamento_existe(8, conn) is False

    repo.registrar_auditoria(
        usuario="Operador", acao="TESTE", objeto="7", detalhes="detalhe", connection=conn
    )
    row = conn.execute("SELECT usuario,modulo,acao,objeto,detalhes,resultado FROM auditoria").fetchone()
    assert tuple(row) == ("Operador", "Financeiro", "TESTE", "7", "detalhe", "SUCESSO")
