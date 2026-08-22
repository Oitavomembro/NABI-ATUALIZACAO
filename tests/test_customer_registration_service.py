from __future__ import annotations

import sqlite3
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
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
                    numero_ficha INTEGER,
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

    def test_edicao_rejeita_nome_ficha_e_limite_invalidos(self) -> None:
        primeiro = self.service.criar(nome="Primeiro", numero_ficha=10, codigo="C1")
        self.service.criar(nome="Segundo", numero_ficha=20, codigo="C2")
        invalidos = (
            ({"nome": "", "numero_ficha": 10, "limite": 0}, "Nome"),
            ({"nome": "Primeiro", "numero_ficha": 0, "limite": 0}, "ficha"),
            ({"nome": "Primeiro", "numero_ficha": -1, "limite": 0}, "ficha"),
            ({"nome": "Primeiro", "numero_ficha": 20, "limite": 0}, "ficha já existe"),
            ({"nome": "Primeiro", "numero_ficha": 10, "limite": -1}, "negativo"),
        )
        for values, message in invalidos:
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, message):
                    self.service.editar(primeiro, codigo="C1", **values)

    def test_edicao_valida_preserva_id_saldo_e_vinculos(self) -> None:
        cliente_id = self.service.criar(nome="Cliente", numero_ficha=10, codigo="C1")
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY,cliente_id INTEGER);
                CREATE TABLE parcelas(id INTEGER PRIMARY KEY,movimentacao_id INTEGER);
                INSERT INTO movimentacoes VALUES(100,1);
                INSERT INTO parcelas VALUES(200,100);
                UPDATE clientes SET saldo_devedor=75 WHERE id=1;
                """
            )
            connection.commit()
        self.service.editar(
            cliente_id, nome="  Cliente   Atualizado ", codigo="C1",
            numero_ficha=11, limite="500,50", telefone=" 9999 ",
        )
        with closing(sqlite3.connect(self.db_path)) as connection:
            customer = connection.execute(
                "SELECT id,nome,numero_ficha,limite,saldo_devedor FROM clientes WHERE id=?",
                (cliente_id,),
            ).fetchone()
            movement = connection.execute("SELECT cliente_id FROM movimentacoes WHERE id=100").fetchone()
            installment = connection.execute("SELECT movimentacao_id FROM parcelas WHERE id=200").fetchone()
        self.assertEqual(customer, (cliente_id, "Cliente Atualizado", 11, 500.5, 75.0))
        self.assertEqual(movement, (cliente_id,))
        self.assertEqual(installment, (100,))
        self.assertEqual(self.history[-1], (cliente_id, "EDIÇÃO", "Dados cadastrais atualizados."))

    def test_criacao_concorrente_serializa_ficha_sem_unique(self) -> None:
        barrier = threading.Barrier(2)

        def create(code: str) -> str:
            service = CustomerRegistrationService(
                ClienteRepository(DatabaseManager(self.db_path, timeout=5)),
                get_config=self.config.get,
                set_config=lambda key, value: self.config.__setitem__(key, value),
            )
            barrier.wait(timeout=5)
            try:
                service.criar(nome=f"Cliente {code}", numero_ficha=77, codigo=code)
            except ValueError as exc:
                return str(exc)
            return "CRIADO"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, ("A77", "B77")))

        self.assertEqual(results.count("CRIADO"), 1)
        self.assertEqual(sum("ficha já existe" in result for result in results), 1)
        with closing(sqlite3.connect(self.db_path)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM clientes WHERE numero_ficha=77"
            ).fetchone()[0]
            self.assertEqual(count, 1)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_edicao_concorrente_serializa_ficha_sem_unique(self) -> None:
        first = self.service.criar(nome="Primeiro", numero_ficha=10, codigo="C10")
        second = self.service.criar(nome="Segundo", numero_ficha=20, codigo="C20")
        barrier = threading.Barrier(2)

        def edit(customer_id: int, code: str) -> str:
            service = CustomerRegistrationService(
                ClienteRepository(DatabaseManager(self.db_path, timeout=5)),
                get_config=self.config.get,
                set_config=lambda key, value: self.config.__setitem__(key, value),
            )
            barrier.wait(timeout=5)
            try:
                service.editar(
                    customer_id, nome=f"Editado {code}", codigo=code,
                    numero_ficha=88, limite=0,
                )
            except ValueError as exc:
                return str(exc)
            return "EDITADO"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda args: edit(*args), ((first, "C10"), (second, "C20"))
            ))

        self.assertEqual(results.count("EDITADO"), 1)
        self.assertEqual(sum("ficha já existe" in result for result in results), 1)
        with closing(sqlite3.connect(self.db_path)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM clientes WHERE numero_ficha=88"
            ).fetchone()[0]
            self.assertEqual(count, 1)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
