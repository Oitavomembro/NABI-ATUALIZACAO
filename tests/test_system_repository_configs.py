import sqlite3

import pytest

from repositories.system_repository import SystemRepository


def test_set_configs_grava_conjunto_em_uma_transacao(tmp_path):
    path = tmp_path / "config.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT)")
    connection.commit(); connection.close()

    repository = SystemRepository(lambda: sqlite3.connect(path))
    repository.set_configs({"a": "1", "b": "2"})

    connection = sqlite3.connect(path)
    assert connection.execute(
        "SELECT chave, valor FROM configuracoes ORDER BY chave"
    ).fetchall() == [("a", "1"), ("b", "2")]
    connection.close()


def test_set_configs_rejeita_chave_invalida_sem_gravar_parcial(tmp_path):
    path = tmp_path / "config.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT)")
    connection.commit(); connection.close()
    repository = SystemRepository(lambda: sqlite3.connect(path))

    with pytest.raises(ValueError):
        repository.set_configs({"valida": "1", "  ": "2"})

    connection = sqlite3.connect(path)
    assert connection.execute("SELECT * FROM configuracoes").fetchall() == []
    connection.close()
