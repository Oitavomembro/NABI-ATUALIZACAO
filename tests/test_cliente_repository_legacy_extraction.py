import sqlite3

from database import DatabaseManager
from repositories import ClienteRepository


def test_get_or_create_final_consumer_is_idempotent(tmp_path):
    database_path = tmp_path / "clientes.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """CREATE TABLE clientes(
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               codigo TEXT UNIQUE,
               numero_ficha INTEGER,
               nome TEXT,
               cpf TEXT,
               rg TEXT,
               telefone TEXT,
               endereco TEXT,
               observacoes TEXT,
               limite REAL,
               saldo_devedor REAL,
               ficticio INTEGER
           )"""
    )
    connection.commit()
    connection.close()
    repository = ClienteRepository(DatabaseManager(database_path))
    first = repository.get_or_create_final_consumer()
    second = repository.get_or_create_final_consumer()
    assert first == second


def test_sales_row_order_is_shared_with_legacy_rule():
    rows = [
        (2, "B", "Casa Ana", None, "", ""),
        (1, "A", "Ana Clara", None, "", ""),
        (3, "C", "Joana", None, "", ""),
    ]
    assert [row[0] for row in ClienteRepository.sort_sales_rows(rows, "ana")] == [1, 3, 2]
