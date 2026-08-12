from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def configure_connection(
    connection: sqlite3.Connection,
    *,
    timeout: float = 30,
    network_mode: bool = False,
    apply_journal: bool = True,
    logger: logging.Logger | None = None,
) -> sqlite3.Connection:
    """Aplica a configuração SQLite padrão do NabiCode a uma conexão aberta."""
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout={max(0, int(timeout * 1000))}")
    connection.execute("PRAGMA foreign_keys=ON")
    if apply_journal:
        try:
            if network_mode:
                connection.execute("PRAGMA journal_mode=DELETE")
                connection.execute("PRAGMA synchronous=FULL")
            else:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.Error as exc:
            (logger or logging.getLogger("NabiCode.Database")).warning(
                "Falha ao aplicar PRAGMAs de journal: %s", exc
            )
    return connection


def open_connection(
    database_path: str | os.PathLike[str],
    *,
    timeout: float = 30,
    network_mode: bool = False,
    apply_journal: bool = True,
    logger: logging.Logger | None = None,
) -> sqlite3.Connection:
    path = Path(database_path).expanduser()
    connection = sqlite3.connect(str(path), timeout=timeout)
    try:
        return configure_connection(
            connection,
            timeout=timeout,
            network_mode=network_mode,
            apply_journal=apply_journal,
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
    write: bool = False,
    logger: logging.Logger | None = None,
) -> Iterator[sqlite3.Connection]:
    """Abre e fecha uma conexão, com commit/rollback explícitos quando write=True."""
    connection = open_connection(
        database_path,
        timeout=timeout,
        network_mode=network_mode,
        apply_journal=apply_journal,
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
        logger=logger,
    )
    destination: sqlite3.Connection | None = None
    try:
        destination = open_connection(
            destination_path,
            timeout=timeout,
            apply_journal=False,
            logger=logger,
        )
        source.backup(destination)
        destination.commit()
    finally:
        if destination is not None:
            destination.close()
        source.close()
