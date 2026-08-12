from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from database import DatabaseManager
from services.customer_maintenance_service import CustomerMaintenanceService


class CustomerMaintenanceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "clientes.db"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE clientes (
                    id INTEGER PRIMARY KEY,
                    numero_ficha INTEGER,
                    codigo TEXT,
                    nome TEXT,
                    cpf TEXT,
                    rg TEXT,
                    telefone TEXT,
                    endereco TEXT,
                    limite REAL,
                    saldo_devedor REAL,
                    observacoes TEXT,
                    ficticio INTEGER DEFAULT 0
                );
                CREATE TABLE movimentacoes (
                    id INTEGER PRIMARY KEY,
                    cliente_id INTEGER
                );
                CREATE TABLE parcelas (
                    id INTEGER PRIMARY KEY,
                    movimentacao_id INTEGER
                );
                CREATE TABLE historico_clientes (
                    id INTEGER PRIMARY KEY,
                    cliente_id INTEGER
                );
                """
            )
            connection.commit()
        self.service = CustomerMaintenanceService(DatabaseManager(self.db_path))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_delete_fictitious_customers_removes_dependents_only(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "INSERT INTO clientes VALUES (1, 1, 'F1', 'FICTICIO', '', '', '', '', 0, 0, '', 1)"
            )
            connection.execute(
                "INSERT INTO clientes VALUES (2, 2, 'R1', 'REAL', '', '', '', '', 0, 0, '', 0)"
            )
            connection.execute("INSERT INTO movimentacoes VALUES (10, 1)")
            connection.execute("INSERT INTO movimentacoes VALUES (20, 2)")
            connection.execute("INSERT INTO parcelas VALUES (100, 10)")
            connection.execute("INSERT INTO parcelas VALUES (200, 20)")
            connection.execute("INSERT INTO historico_clientes VALUES (1000, 1)")
            connection.execute("INSERT INTO historico_clientes VALUES (2000, 2)")
            connection.commit()

        self.assertEqual(self.service.delete_fictitious_customers(), 1)
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM parcelas").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM historico_clientes").fetchone()[0], 1)

    def test_delete_fictitious_customers_rolls_back_on_failure(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "INSERT INTO clientes VALUES (1, 1, 'F1', 'FICTICIO', '', '', '', '', 0, 0, '', 1)"
            )
            connection.execute("DROP TABLE historico_clientes")
            connection.commit()
        with self.assertRaises(sqlite3.OperationalError):
            self.service.delete_fictitious_customers()
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 1)


    def test_recreate_demo_customers_is_idempotent(self) -> None:
        self.assertEqual(self.service.recreate_demo_customers(), 3)
        self.assertEqual(self.service.recreate_demo_customers(), 0)
        with closing(sqlite3.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT codigo, nome, ficticio FROM clientes ORDER BY codigo"
            ).fetchall()
        self.assertEqual(
            rows,
            [
                ("CLI001", "Ana Souza", 1),
                ("CLI002", "Bruno Lima", 1),
                ("CLI003", "Carla Mendes", 1),
            ],
        )

    def test_recreate_demo_customers_rolls_back_on_failure(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("DROP TABLE clientes")
            connection.commit()
        with self.assertRaises(sqlite3.OperationalError):
            self.service.recreate_demo_customers()

    def test_export_csv_writes_header_and_rows(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "INSERT INTO clientes VALUES (1, 5, 'C5', 'ÁLVARO', '123', 'RG', '999', 'RUA', 100, 25, 'OBS', 0)"
            )
            connection.commit()
        output = self.service.export_csv(Path(self.tmp.name) / "clientes")
        self.assertEqual(output.suffix, ".csv")
        with output.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle, delimiter=";"))
        self.assertEqual(rows[0][0:3], ["Ficha", "Código", "Nome"])
        self.assertEqual(rows[1][0:3], ["5", "C5", "ÁLVARO"])

    def test_export_csv_does_not_leave_temporary_file_on_failure(self) -> None:
        destination = Path(self.tmp.name) / "blocked.csv"
        destination.mkdir()
        with self.assertRaises(OSError):
            self.service.export_csv(destination)
        self.assertFalse((destination.parent / ".blocked.csv.tmp").exists())


if __name__ == "__main__":
    unittest.main()
