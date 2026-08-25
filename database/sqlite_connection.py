from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class SQLitePragmaPolicyError(sqlite3.DatabaseError):
    """A conexão não oferece as garantias SQLite exigidas pelo perfil."""


def _pragma_scalar(connection: sqlite3.Connection, name: str):
    row = connection.execute(f"PRAGMA {name}").fetchone()
    if row is None:
        raise SQLitePragmaPolicyError(f"SQLite não informou o valor efetivo de PRAGMA {name}.")
    return row[0]


def effective_pragmas(connection: sqlite3.Connection) -> dict[str, int | str]:
    """Lê a política efetiva; nunca presume que um PRAGMA solicitado foi aceito."""
    return {
        "foreign_keys": int(_pragma_scalar(connection, "foreign_keys")),
        "journal_mode": str(_pragma_scalar(connection, "journal_mode")).casefold(),
        "synchronous": int(_pragma_scalar(connection, "synchronous")),
        "busy_timeout": int(_pragma_scalar(connection, "busy_timeout")),
        "query_only": int(_pragma_scalar(connection, "query_only")),
    }


def _is_memory_database(connection: sqlite3.Connection) -> bool:
    rows = connection.execute("PRAGMA database_list").fetchall()
    return not rows or all(not str(row[2] or "").strip() for row in rows)


def _require_effective(actual: dict[str, int | str], expected: dict[str, int | str], profile: str) -> None:
    differences = [
        f"{name}: esperado={value!r}, efetivo={actual.get(name)!r}"
        for name, value in expected.items() if actual.get(name) != value
    ]
    if differences:
        raise SQLitePragmaPolicyError(
            f"Política SQLite {profile} não pôde ser garantida (" + "; ".join(differences) + "). "
            "O banco não foi liberado para uso; verifique permissões, filesystem e suporte do SQLite."
        )


def _set_journal_mode(connection: sqlite3.Connection, expected: str, timeout: float) -> None:
    """Tolera somente a disputa transitória entre conexões que aplicam o mesmo modo."""
    deadline = time.monotonic() + min(max(float(timeout), 0.0), 2.0)
    while True:
        try:
            connection.execute(f"PRAGMA journal_mode={expected}")
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).casefold():
                raise
            try:
                if str(_pragma_scalar(connection, "journal_mode")).casefold() == expected.casefold():
                    return
            except sqlite3.Error:
                pass
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def configure_connection(
    connection: sqlite3.Connection,
    *,
    timeout: float = 30,
    network_mode: bool = False,
    apply_journal: bool = True,
    read_only: bool = False,
    logger: logging.Logger | None = None,
) -> sqlite3.Connection:
    """Aplica e comprova a política SQLite antes de liberar a conexão."""
    connection.row_factory = sqlite3.Row
    timeout_ms = max(0, int(timeout * 1000))
    profile = "somente leitura/diagnóstico" if read_only or not apply_journal else "rede DELETE/FULL" if network_mode else "local WAL/NORMAL"
    try:
        connection.execute(f"PRAGMA busy_timeout={timeout_ms}")
        connection.execute("PRAGMA foreign_keys=ON")
        if read_only or not apply_journal:
            connection.execute("PRAGMA query_only=ON")
        else:
            connection.execute("PRAGMA query_only=OFF")
            memory = _is_memory_database(connection)
            journal = "MEMORY" if memory else "DELETE" if network_mode else "WAL"
            _set_journal_mode(connection, journal, timeout)
            connection.execute(f"PRAGMA synchronous={'FULL' if network_mode else 'NORMAL'}")
        actual = effective_pragmas(connection)
        expected: dict[str, int | str] = {
            "foreign_keys": 1, "busy_timeout": timeout_ms,
            "query_only": 1 if read_only or not apply_journal else 0,
        }
        if not read_only and apply_journal:
            expected.update({
                "journal_mode": "memory" if memory else "delete" if network_mode else "wal",
                "synchronous": 2 if network_mode else 1,
            })
        _require_effective(actual, expected, profile)
    except SQLitePragmaPolicyError:
        raise
    except sqlite3.Error as exc:
        (logger or logging.getLogger("NabiCode.Database")).error(
            "Falha ao garantir política SQLite %s: %s", profile, exc
        )
        raise SQLitePragmaPolicyError(
            f"Não foi possível garantir a política SQLite {profile}: {exc}. O banco não foi liberado para uso."
        ) from exc
    return connection


def open_connection(
    database_path: str | os.PathLike[str],
    *,
    timeout: float = 30,
    network_mode: bool = False,
    apply_journal: bool = True,
    read_only: bool = False,
    logger: logging.Logger | None = None,
) -> sqlite3.Connection:
    raw_path = str(database_path)
    if raw_path == ":memory:":
        target, uri = raw_path, False
    else:
        path = Path(database_path).expanduser().resolve()
        target = path.as_uri() + "?mode=ro" if read_only else str(path)
        uri = bool(read_only)
    connection = sqlite3.connect(target, timeout=timeout, uri=uri)
    try:
        return configure_connection(
            connection,
            timeout=timeout,
            network_mode=network_mode,
            apply_journal=apply_journal,
            read_only=read_only,
            logger=logger,
        )
    except Exception:
        connection.close()
        raise


@contextmanager
def connection_session(
    database_path: str | os.PathLike[str],
    *,
    timeout: float = 30,
    network_mode: bool = False,
    apply_journal: bool = True,
    read_only: bool = False,
    write: bool = False,
    logger: logging.Logger | None = None,
) -> Iterator[sqlite3.Connection]:
    """Abre e fecha uma conexão, com commit/rollback explícitos quando write=True."""
    if write and (read_only or not apply_journal):
        raise SQLitePragmaPolicyError(
            "Uma sessão somente leitura/diagnóstico não pode ser aberta como escrita."
        )
    connection = open_connection(
        database_path,
        timeout=timeout,
        network_mode=network_mode,
        apply_journal=apply_journal,
        read_only=read_only,
        logger=logger,
    )
    try:
        yield connection
        if write:
            connection.commit()
    except Exception:
        if write:
            connection.rollback()
        if logger is not None:
            logger.exception("Transação SQLite revertida em %s", database_path)
        raise
    finally:
        connection.close()


def backup_database(
    source_path: str | os.PathLike[str],
    destination_path: str | os.PathLike[str],
    *,
    timeout: float = 60,
    network_mode: bool = False,
    logger: logging.Logger | None = None,
) -> None:
    """Cria backup consistente e fecha as duas conexões mesmo em falha."""
    source = open_connection(
        source_path,
        timeout=timeout,
        network_mode=network_mode,
        apply_journal=False,
        read_only=True,
        logger=logger,
    )
    destination: sqlite3.Connection | None = None
    try:
        destination = open_connection(
            destination_path,
            timeout=timeout,
            network_mode=False,
            apply_journal=True,
            logger=logger,
        )
        source.backup(destination)
        destination.commit()
    finally:
        if destination is not None:
            destination.close()
        source.close()
