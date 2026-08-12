from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from repositories import CadastroAuxiliarRepository
from repositories.customer_maintenance_repository import CustomerMaintenanceRepository
from repositories.fornecedor_repository import FornecedorRepository


class CadastroRepositoryExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "cadastros.db"
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, numero_ficha INTEGER,
                nome TEXT, cpf TEXT, rg TEXT, telefone TEXT, endereco TEXT,
                observacoes TEXT, limite REAL, saldo_devedor REAL, ficticio INTEGER DEFAULT 0
            );
            CREATE TABLE movimentacoes (id INTEGER PRIMARY KEY, cliente_id INTEGER);
            CREATE TABLE parcelas (id INTEGER PRIMARY KEY, movimentacao_id INTEGER);
            CREATE TABLE historico_clientes (id INTEGER PRIMARY KEY, cliente_id INTEGER);
            CREATE TABLE fornecedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT, razao_social TEXT, nome_fantasia TEXT,
                cnpj TEXT, telefone TEXT, email TEXT, ativo INTEGER,
                criado_em TEXT, atualizado_em TEXT
            );
            CREATE TABLE marcas_produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, ativo INTEGER,
                criado_em TEXT, atualizado_em TEXT
            );
            CREATE TABLE unidades_medida (
                id INTEGER PRIMARY KEY AUTOINCREMENT, sigla TEXT, descricao TEXT,
                permite_fracionado INTEGER, ativo INTEGER, criado_em TEXT, atualizado_em TEXT
            );
            """
        )
        connection.commit()
        connection.close()
        self.database = DatabaseManager(str(self.db_path))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_customer_maintenance_repository_is_idempotent_and_exports(self) -> None:
        repository = CustomerMaintenanceRepository(self.database)
        demo = [("CLI001", 1, "Ana", "", "", "", "", "", 100.0, 0.0, 1)]
        self.assertEqual(repository.create_missing_demo_customers(demo), 1)
        self.assertEqual(repository.create_missing_demo_customers(demo), 0)
        self.assertEqual(repository.export_rows()[0][2], "Ana")
        self.assertEqual(repository.delete_fictitious(), 1)

    def test_demo_customer_batch_rejects_duplicate_code_or_record(self) -> None:
        repository = CustomerMaintenanceRepository(self.database)
        demo = [
            ("CLI001", 1, "Ana", "", "", "", "", "", 100.0, 0.0, 1),
            ("CLI001", 2, "Código repetido", "", "", "", "", "", 0.0, 0.0, 1),
            ("CLI003", 1, "Ficha repetida", "", "", "", "", "", 0.0, 0.0, 1),
            ("CLI004", 4, "Bruno", "", "", "", "", "", 0.0, 0.0, 1),
        ]

        self.assertEqual(repository.create_missing_demo_customers(demo), 2)
        self.assertEqual(
            [row[2] for row in repository.export_rows()],
            ["Ana", "Bruno"],
        )

    def test_delete_fictitious_removes_only_related_rows(self) -> None:
        repository = CustomerMaintenanceRepository(self.database)
        with self.database.session(write=True) as connection:
            connection.execute(
                "INSERT INTO clientes(id,codigo,numero_ficha,nome,ficticio) VALUES(1,'F',1,'Fictício',1)"
            )
            connection.execute(
                "INSERT INTO clientes(id,codigo,numero_ficha,nome,ficticio) VALUES(2,'R',2,'Real',0)"
            )
            connection.execute("INSERT INTO movimentacoes(id,cliente_id) VALUES(10,1)")
            connection.execute("INSERT INTO movimentacoes(id,cliente_id) VALUES(20,2)")
            connection.execute("INSERT INTO parcelas(id,movimentacao_id) VALUES(100,10)")
            connection.execute("INSERT INTO parcelas(id,movimentacao_id) VALUES(200,20)")
            connection.execute("INSERT INTO historico_clientes(id,cliente_id) VALUES(1000,1)")
            connection.execute("INSERT INTO historico_clientes(id,cliente_id) VALUES(2000,2)")

        self.assertEqual(repository.delete_fictitious(), 1)
        with self.database.session() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM parcelas").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM historico_clientes").fetchone()[0], 1)

    def test_delete_fictitious_returns_zero_without_writes(self) -> None:
        repository = CustomerMaintenanceRepository(self.database)
        self.assertEqual(repository.delete_fictitious(), 0)

    def test_delete_fictitious_handles_multiple_customers_in_one_batch(self) -> None:
        repository = CustomerMaintenanceRepository(self.database)
        with self.database.session(write=True) as connection:
            for customer_id in (1, 2):
                connection.execute(
                    "INSERT INTO clientes(id,codigo,numero_ficha,nome,ficticio) VALUES(?,?,?,?,1)",
                    (customer_id, f"F{customer_id}", customer_id, f"Fictício {customer_id}"),
                )
                movement_id = customer_id * 10
                connection.execute(
                    "INSERT INTO movimentacoes(id,cliente_id) VALUES(?,?)",
                    (movement_id, customer_id),
                )
                connection.execute(
                    "INSERT INTO parcelas(id,movimentacao_id) VALUES(?,?)",
                    (customer_id * 100, movement_id),
                )
                connection.execute(
                    "INSERT INTO historico_clientes(id,cliente_id) VALUES(?,?)",
                    (customer_id * 1000, customer_id),
                )

        self.assertEqual(repository.delete_fictitious(), 2)
        with self.database.session() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM parcelas").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM historico_clientes").fetchone()[0], 0)

    def test_supplier_queries_are_delegated_to_supplier_repository(self) -> None:
        supplier_repository = FornecedorRepository(self.database)
        auxiliary_repository = CadastroAuxiliarRepository(
            self.database, fornecedores=supplier_repository
        )
        supplier_id = auxiliary_repository.criar(
            "fornecedor", "Fornecedor A", cnpj="12.345.678/0001-00"
        )
        self.assertGreater(supplier_id, 0)
        self.assertEqual(
            auxiliary_repository.listar_ativos("fornecedor"),
            [{"id": supplier_id, "nome": "Fornecedor A"}],
        )


if __name__ == "__main__":
    unittest.main()
