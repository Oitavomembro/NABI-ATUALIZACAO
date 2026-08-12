from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.sqlite_connection import backup_database, connection_session, open_connection


class SQLiteConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.database = Path(self.tmp.name) / "main.db"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_open_connection_applies_standard_pragmas(self) -> None:
        connection = open_connection(self.database)
        try:
            self.assertIs(connection.row_factory, sqlite3.Row)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertGreaterEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 30000)
        finally:
            connection.close()

    def test_write_session_commits_and_rolls_back(self) -> None:
        with connection_session(self.database, write=True) as connection:
            connection.execute("CREATE TABLE dados (id INTEGER PRIMARY KEY, nome TEXT)")
            connection.execute("INSERT INTO dados (nome) VALUES ('OK')")

        with self.assertRaises(RuntimeError):
            with connection_session(self.database, write=True) as connection:
                connection.execute("INSERT INTO dados (nome) VALUES ('ROLLBACK')")
                raise RuntimeError("falha controlada")

        with connection_session(self.database) as connection:
            rows = connection.execute("SELECT nome FROM dados ORDER BY id").fetchall()
        self.assertEqual([row[0] for row in rows], ["OK"])

    def test_backup_database_creates_consistent_copy(self) -> None:
        with connection_session(self.database, write=True) as connection:
            connection.execute("CREATE TABLE dados (valor TEXT)")
            connection.execute("INSERT INTO dados VALUES ('preservado')")
        destination = Path(self.tmp.name) / "backup.db"
        backup_database(self.database, destination)
        with connection_session(destination, apply_journal=False) as connection:
            self.assertEqual(connection.execute("SELECT valor FROM dados").fetchone()[0], "preservado")
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_backup_closes_source_when_destination_open_fails(self) -> None:
        class SourceConnection:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        source = SourceConnection()
        with patch(
            "database.sqlite_connection.open_connection",
            side_effect=[source, sqlite3.OperationalError("destino indisponÃ­vel")],
        ):
            with self.assertRaises(sqlite3.OperationalError):
                backup_database("origem.db", "destino.db")
        self.assertTrue(source.closed)


if __name__ == "__main__":
    unittest.main()
