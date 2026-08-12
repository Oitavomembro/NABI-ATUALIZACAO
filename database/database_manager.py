from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence, Any

from .sqlite_connection import open_connection


class DatabaseManager:
    """Centraliza conexões e transações SQLite sem conhecer a interface gráfica."""

    def __init__(
        self,
        database_path: str | os.PathLike[str],
        *,
        network_mode: bool = False,
        timeout: float = 30,
        logger: logging.Logger | None = None,
    ) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.network_mode = bool(network_mode)
        self.timeout = timeout
        self.logger = logger or logging.getLogger("NabiCode.Database")

    def connect(self) -> sqlite3.Connection:
        return open_connection(
            self.database_path,
            timeout=self.timeout,
            network_mode=self.network_mode,
            logger=self.logger,
        )

    @contextmanager
    def session(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            if write:
                connection.commit()
        except Exception:
            if write:
                connection.rollback()
            self.logger.exception("Transação SQLite revertida em %s", self.database_path)
            raise
        finally:
            connection.close()

    def fetch_all(self, sql: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self.session() as connection:
            return connection.execute(sql, tuple(parameters)).fetchall()

    def fetch_one(self, sql: str, parameters: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self.session() as connection:
            return connection.execute(sql, tuple(parameters)).fetchone()

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> int:
        with self.session(write=True) as connection:
            cursor = connection.execute(sql, tuple(parameters))
            return int(cursor.lastrowid or 0)
