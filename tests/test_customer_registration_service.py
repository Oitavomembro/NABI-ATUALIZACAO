from __future__ import annotations

import sqlite3
import json
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
                    ,email TEXT, inscricao_estadual TEXT, contribuinte_icms INTEGER,
                    fiscal_logradouro TEXT, fiscal_numero TEXT, fiscal_bairro TEXT,
                    fiscal_codigo_municipio TEXT, fiscal_municipio TEXT,
                    fiscal_uf TEXT, fiscal_cep TEXT
                );
                CREATE TABLE assistant_operation_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    operation_kind TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL DEFAULT '',
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    committed_at TEXT NOT NULL DEFAULT ''
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

    def test_padrao_fiscal_vem_da_instalacao_e_perfil_editado_e_persistido(self) -> None:
        self.config["fiscal.config.v1"] = json.dumps({
            "state": "BA",
            "issuer": {"city": "ITABUNA", "city_code": "2914802", "state": "BA"},
        })
        self.assertEqual(self.service.fiscal_address_defaults(), {
            "fiscal_city": "ITABUNA", "fiscal_city_code": "2914802", "fiscal_state": "BA",
        })
        customer_id = self.service.criar(
            nome="Cliente Fiscal", codigo="FISCAL", fiscal_logradouro="RUA A",
            fiscal_numero="10", fiscal_bairro="CENTRO", fiscal_municipio="ILHÉUS",
            fiscal_codigo_municipio="2913606", fiscal_uf="BA", fiscal_cep="",
        )
        self.service.editar(
            customer_id, nome="Cliente Fiscal", codigo="FISCAL",
            fiscal_logradouro="RUA B", fiscal_numero="20", fiscal_bairro="BAIRRO",
            fiscal_municipio="ITABUNA", fiscal_codigo_municipio="2914802",
            fiscal_uf="ba", fiscal_cep="45600000", email="fiscal@example.com",
        )
        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                """SELECT email,fiscal_logradouro,fiscal_numero,fiscal_bairro,
                          fiscal_codigo_municipio,fiscal_municipio,fiscal_uf,fiscal_cep
                     FROM clientes WHERE id=?""", (customer_id,),
            ).fetchone()
        self.assertEqual(row, (
            "fiscal@example.com", "RUA B", "20", "BAIRRO", "2914802",
            "ITABUNA", "BA", "45600000",
        ))

    def test_cadastro_assistido_e_idempotente_e_atomico(self) -> None:
        fingerprint = "a" * 64
        first = self.service.criar_assistido(
            nome="Cliente Nabi", numero_ficha=5500, limite="100,00",
            usuario="operador", idempotency_key="nabi:customer:1",
            operation_fingerprint=fingerprint,
        )
        repeated = self.service.criar_assistido(
            nome="Cliente Nabi", numero_ficha=5500, limite="100,00",
            usuario="operador", idempotency_key="nabi:customer:1",
            operation_fingerprint=fingerprint,
        )
        self.assertEqual(first, repeated)
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 1)
            journal = connection.execute(
                "SELECT operation_kind,status,username FROM assistant_operation_journal"
            ).fetchone()
        self.assertEqual(journal, ("CUSTOMER_CREATE", "COMMITTED", "operador"))
        with self.assertRaises(PermissionError):
            self.service.criar_assistido(
                nome="Outro", numero_ficha=5501, usuario="operador",
                idempotency_key="nabi:customer:1", operation_fingerprint="b" * 64,
            )
        with self.assertRaisesRegex(ValueError, "ficha já existe"):
            self.service.criar_assistido(
                nome="Duplicado", numero_ficha=5500, usuario="operador",
                idempotency_key="nabi:customer:2", operation_fingerprint="c" * 64,
            )
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertIsNone(connection.execute(
                "SELECT status FROM assistant_operation_journal WHERE idempotency_key=?",
                ("nabi:customer:2",),
            ).fetchone())

    def test_cadastro_assistido_exige_autoria_e_fingerprint_reais(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.criar_assistido(
                nome="Sem ator", numero_ficha=5500, usuario="",
                idempotency_key="nabi:customer:3", operation_fingerprint="d" * 64,
            )
        with self.assertRaisesRegex(ValueError, "digital"):
            self.service.criar_assistido(
                nome="Sem hash", numero_ficha=5500, usuario="op",
                idempotency_key="nabi:customer:4", operation_fingerprint="invalida",
            )

    def test_rejeita_nome_vazio_ficha_duplicada_e_limite_negativo(self) -> None:
        with self.assertRaisesRegex(ValueError, "Nome"):
            self.service.criar(nome="")
        self.service.criar(nome="Primeiro", numero_ficha=10, codigo="C1")
        with self.assertRaisesRegex(ValueError, "ficha já existe"):
            self.service.criar(nome="Segundo", numero_ficha=10, codigo="C2")
        with self.assertRaisesRegex(ValueError, "não pode ser negativo"):
            self.service.criar(nome="Terceiro", limite="-1")

    def test_codigo_ibge_precisa_pertencer_a_uf_informada(self) -> None:
        with self.assertRaisesRegex(ValueError, "não pertence"):
            self.service.criar(
                nome="Localidade inválida", fiscal_municipio="ITABUNA",
                fiscal_codigo_municipio="2914802", fiscal_uf="SP",
            )

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

    def test_exclui_somente_cadastro_sem_saldo_ou_movimento(self) -> None:
        vazio = self.service.criar(nome="Cadastro duplicado", numero_ficha=31, codigo="VAZIO")
        self.service.excluir_cadastro_sem_movimento(vazio)
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertIsNone(
                connection.execute("SELECT id FROM clientes WHERE id=?", (vazio,)).fetchone()
            )

        com_saldo = self.service.criar(nome="Com saldo", numero_ficha=32, codigo="SALDO")
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "UPDATE clientes SET saldo_devedor=10 WHERE id=?", (com_saldo,)
            )
            connection.commit()
        with self.assertRaisesRegex(ValueError, "saldo devedor"):
            self.service.excluir_cadastro_sem_movimento(com_saldo)

        com_movimento = self.service.criar(
            nome="Com movimento", numero_ficha=33, codigo="MOV"
        )
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, cliente_id INTEGER)"
            )
            connection.execute(
                "INSERT INTO movimentacoes(id, cliente_id) VALUES(1, ?)",
                (com_movimento,),
            )
            connection.commit()
        with self.assertRaisesRegex(ValueError, "histórico comercial"):
            self.service.excluir_cadastro_sem_movimento(com_movimento)

    def test_exclusao_recusa_consumidor_final(self) -> None:
        consumer = self.service.criar(
            nome="Consumidor Final", numero_ficha=None, codigo="CONSUMIDOR_FINAL"
        )
        with self.assertRaisesRegex(ValueError, "cadastro técnico"):
            self.service.excluir_cadastro_sem_movimento(consumer)

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
