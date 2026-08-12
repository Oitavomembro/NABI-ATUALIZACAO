from __future__ import annotations

import os
from contextlib import contextmanager

from database.sqlite_connection import connection_session, open_connection


class SQLiteRuntimeAdapter:
    def __init__(self, database_path: str, *, network_mode: bool, logger) -> None:
        self.database_path = database_path
        self.network_mode = bool(network_mode)
        self.logger = logger

    def connect(self, caminho=None, timeout: int = 30):
        target = caminho or self.database_path
        primary = os.path.abspath(target) == os.path.abspath(self.database_path)
        return open_connection(
            target,
            timeout=timeout,
            network_mode=bool(self.network_mode and primary),
            apply_journal=primary,
            logger=self.logger,
        )

    @contextmanager
    def session(self, caminho=None, timeout: int = 30, escrita: bool = False):
        target = caminho or self.database_path
        primary = os.path.abspath(target) == os.path.abspath(self.database_path)
        with connection_session(
            target,
            timeout=timeout,
            network_mode=bool(self.network_mode and primary),
            apply_journal=primary,
            write=escrita,
            logger=self.logger,
        ) as connection:
            yield connection
