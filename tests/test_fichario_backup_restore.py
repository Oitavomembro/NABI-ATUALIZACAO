from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from database.maintenance import DatabaseMaintenanceService


TABLES = ("clientes", "produtos", "movimentacoes", "parcelas", "configuracoes", "historico_clientes")


def create_database(path: Path, schema=20) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(f"""
        CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
        INSERT INTO configuracoes VALUES('db_schema_version', '{schema}');
        INSERT INTO configuracoes VALUES('empresa_nome', 'LOJA TESTE');
        CREATE TABLE clientes(id INTEGER PRIMARY KEY, numero_ficha INTEGER, nome TEXT, saldo_devedor REAL);
        INSERT INTO clientes VALUES(7, 7007, 'MARIA', 150.00);
        CREATE TABLE produtos(id INTEGER PRIMARY KEY, nome TEXT, preco REAL, estoque REAL);
        INSERT INTO produtos VALUES(9, 'CADEIRA', 100.00, 3);
        CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, cliente_id INTEGER, tipo TEXT, descricao TEXT, valor REAL);
        INSERT INTO movimentacoes VALUES(11, 7, 'COMPRA', '1x CADEIRA (R$ 100.00)', 100.00);
        CREATE TABLE parcelas(id INTEGER PRIMARY KEY, movimentacao_id INTEGER, valor_parcela REAL, status TEXT);
        INSERT INTO parcelas VALUES(13, 11, 100.00, 'PENDENTE');
        CREATE TABLE historico_clientes(id INTEGER PRIMARY KEY, cliente_id INTEGER, evento TEXT);
        INSERT INTO historico_clientes VALUES(15, 7, 'RECEBIMENTO');
    """)
    connection.commit(); connection.close()


@pytest.fixture
def maintenance(tmp_path):
    database = tmp_path / "fichario.db"; create_database(database)
    return DatabaseMaintenanceService(
        database, tmp_path / "backups", expected_schema_version=20, required_tables=TABLES
    )


def snapshot(path: Path):
    connection = sqlite3.connect(path)
    try:
        return {
            "cliente": connection.execute("SELECT numero_ficha,nome,saldo_devedor FROM clientes").fetchall(),
            "produto": connection.execute("SELECT nome,preco,estoque FROM produtos").fetchall(),
            "venda": connection.execute("SELECT cliente_id,descricao,valor FROM movimentacoes").fetchall(),
            "parcela": connection.execute("SELECT movimentacao_id,valor_parcela,status FROM parcelas").fetchall(),
            "historico": connection.execute("SELECT cliente_id,evento FROM historico_clientes").fetchall(),
            "config": connection.execute("SELECT chave,valor FROM configuracoes ORDER BY chave").fetchall(),
        }
    finally:
        connection.close()


def test_ida_e_volta_preserva_dados_fichario(maintenance):
    before = snapshot(maintenance.database_path)
    backup, report = maintenance.create_backup(prefix="fichario")
    assert report.valid
    connection = sqlite3.connect(maintenance.database_path)
    connection.executescript("DELETE FROM historico_clientes; DELETE FROM parcelas; UPDATE clientes SET saldo_devedor=999;")
    connection.commit(); connection.close()
    safety, restored = maintenance.restore(backup)
    assert safety.is_file() and restored.valid
    assert snapshot(maintenance.database_path) == before


def test_corrompido_schema_incompativel_e_caminho_invalido_nao_alteram_atual(maintenance, tmp_path):
    before = snapshot(maintenance.database_path)
    corrupt = tmp_path / "corrupt.db"; corrupt.write_bytes(b"nao e sqlite")
    with pytest.raises(sqlite3.DatabaseError): maintenance.restore(corrupt)
    incompatible = tmp_path / "old.db"; create_database(incompatible, schema=19)
    with pytest.raises(RuntimeError): maintenance.restore(incompatible)
    with pytest.raises(FileNotFoundError): maintenance.restore(tmp_path / "missing.db")
    assert snapshot(maintenance.database_path) == before


def test_falha_no_meio_recupera_copia_anterior(maintenance):
    backup, _ = maintenance.create_backup(prefix="fonte")
    before = snapshot(maintenance.database_path)
    original_connect = maintenance._connect
    calls = {"source": 0}

    class FailingSource(sqlite3.Connection):
        def backup(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("falha simulada")

    def connect(path=None):
        if path is not None and Path(path).resolve() == backup.resolve():
            calls["source"] += 1
            if calls["source"] == 2:
                return sqlite3.connect(str(backup), factory=FailingSource)
        return original_connect(path)

    with patch.object(maintenance, "_connect", side_effect=connect):
        with pytest.raises(sqlite3.OperationalError): maintenance.restore(backup)
    assert snapshot(maintenance.database_path) == before


def test_backup_contem_so_banco_e_nao_licenca_ou_segredos(maintenance):
    backup, _ = maintenance.create_backup(prefix="fichario")
    assert backup.suffix == ".db"
    names = {path.name.casefold() for path in backup.parent.iterdir()}
    assert "current.nabilic" not in names
    assert not any("private" in name or "certificate" in name for name in names)
