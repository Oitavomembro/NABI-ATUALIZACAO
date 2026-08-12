from __future__ import annotations

import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from database import DatabaseManager
from repositories import ClienteRepository
from services.customer_registration_service import CustomerRegistrationService


class CustomerRegistrationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "clientes.db"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE,
                    numero_ficha INTEGER UNIQUE,
                    nome TEXT NOT NULL,
                    cpf TEXT, rg TEXT, telefone TEXT, endereco TEXT,
                    observacoes TEXT, limite REAL, saldo_devedor REAL
                );
                """
            )
        self.config = {"proxima_ficha": "5500"}
        self.history: list[tuple[int, str, str]] = []
        self.service = CustomerRegistrationService(
            ClienteRepository(DatabaseManager(self.db_path)),
            get_config=self.config.get,
            set_config=lambda key, value: self.config.__setitem__(key, value),
            history_callback=lambda customer_id, event, details: self.history.append(
                (customer_id, event, details)
            ),
            now=lambda: datetime(2026, 8, 6, 17, 43, 21),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_criar_normaliza_dados_e_atualiza_proxima_ficha(self) -> None:
        customer_id = self.service.criar(
            nome="  Maria   da Silva ", numero_ficha="5500", limite="1.234,56",
            cpf=" 123 ", telefone=" 9999 ",
        )
        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                "SELECT codigo, numero_ficha, nome, cpf, telefone, limite, saldo_devedor FROM clientes"
            ).fetchone()
        self.assertEqual(row, ("CLI174321", 5500, "Maria da Silva", "123", "9999", 1234.56, 0.0))
        self.assertEqual(self.config["proxima_ficha"], "5501")
        self.assertEqual(self.history, [(customer_id, "CADASTRO", "Cadastro criado.")])

    def test_rejeita_nome_vazio_ficha_duplicada_e_limite_negativo(self) -> None:
        with self.assertRaisesRegex(ValueError, "Nome"):
            self.service.criar(nome="")
        self.service.criar(nome="Primeiro", numero_ficha=10, codigo="C1")
        with self.assertRaisesRegex(ValueError, "ficha já existe"):
            self.service.criar(nome="Segundo", numero_ficha=10, codigo="C2")
        with self.assertRaisesRegex(ValueError, "não pode ser negativo"):
            self.service.criar(nome="Terceiro", limite="-1")


if __name__ == "__main__":
    unittest.main()
