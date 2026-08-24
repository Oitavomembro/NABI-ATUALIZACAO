from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from database import DatabaseManager
from repositories.cliente_repository import ClienteRepository
from repositories.customer_maintenance_repository import CustomerMaintenanceRepository
from services.customer_registration_service import CustomerRegistrationService


class Cadastros2496RobustezTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "cadastros_2496.db"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_ficha INTEGER UNIQUE,
                    codigo TEXT UNIQUE,
                    nome TEXT NOT NULL,
                    saldo_devedor REAL DEFAULT 0,
                    limite REAL DEFAULT 0,
                    telefone TEXT,
                    cpf TEXT,
                    rg TEXT,
                    endereco TEXT,
                    observacoes TEXT,
                    favorito INTEGER DEFAULT 0,
                    ficticio INTEGER DEFAULT 0
                );
                CREATE TABLE historico_clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER NOT NULL,
                    evento TEXT NOT NULL,
                    detalhes TEXT,
                    data TEXT NOT NULL
                );
                CREATE TABLE movimentacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER
                );
                CREATE TABLE parcelas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movimentacao_id INTEGER
                );
                INSERT INTO clientes
                    (numero_ficha,codigo,nome,saldo_devedor,limite,telefone,cpf,rg,endereco,observacoes,favorito,ficticio)
                VALUES
                    (101,'C101','MARIA SILVA',220,500,'(11) 98888-1111','111.111.111-11','','','','1',0),
                    (102,'C102','MARIA JOSE',0,500,'(11) 97777-2222','222.222.222-22','','','','0',0),
                    (103,'C103','AUGUSTO MARIA',0,500,'(11) 96666-3333','333.333.333-33','','','','0',0),
                    (NULL,'LEGACY-1','CLIENTE MIGRADO',35,0,NULL,NULL,NULL,NULL,NULL,0,0);
                """
            )
        self.database = DatabaseManager(self.db_path)
        self.repository = ClienteRepository(self.database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_pesquisa_por_nome_preserva_relevancia_e_ordenacao(self) -> None:
        pagina = self.repository.list_page("maria")
        self.assertEqual(
            [row[2] for row in pagina.rows],
            ["MARIA JOSE", "MARIA SILVA", "AUGUSTO MARIA"],
        )

    def test_pesquisa_por_ficha_exata(self) -> None:
        pagina = self.repository.list_page("102")
        self.assertEqual(pagina.total, 1)
        self.assertEqual(pagina.rows[0][1], 102)
        self.assertEqual(pagina.rows[0][2], "MARIA JOSE")

    def test_pesquisa_por_cpf(self) -> None:
        pagina = self.repository.list_page("222.222.222-22")
        self.assertEqual(pagina.total, 1)
        self.assertEqual(pagina.rows[0][2], "MARIA JOSE")

    def test_pesquisa_por_telefone(self) -> None:
        pagina = self.repository.list_page("98888-1111")
        self.assertEqual(pagina.total, 1)
        self.assertEqual(pagina.rows[0][2], "MARIA SILVA")

    def test_favoritos_preservam_filtro_e_ordenacao(self) -> None:
        pagina = self.repository.list_page("maria", favorites_only=True)
        self.assertEqual([row[2] for row in pagina.rows], ["MARIA SILVA"])

    def test_refresh_apos_atualizacao_financeira_consume_saldo_persistido(self) -> None:
        antes = self.repository.list_page("101")
        self.assertEqual(float(antes.rows[0][3]), 220.0)
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE clientes SET saldo_devedor=200 WHERE numero_ficha=101")
            connection.commit()
        depois = self.repository.list_page("101")
        self.assertEqual(float(depois.rows[0][3]), 200.0)

    def test_dados_migrados_com_campos_nulos_continuam_pesquisaveis(self) -> None:
        pagina = self.repository.list_page("cliente migrado")
        self.assertEqual(pagina.total, 1)
        self.assertIsNone(pagina.rows[0][1])
        self.assertEqual(pagina.rows[0][2], "CLIENTE MIGRADO")
        self.assertEqual(float(pagina.rows[0][3]), 35.0)

    def test_rollback_cadastral_remove_insert_parcial(self) -> None:
        class FailingRepository(ClienteRepository):
            def criar(self, dados, connection=None):
                customer_id = super().criar(dados, connection=connection)
                self._inserted_id = customer_id
                raise RuntimeError("falha simulada após INSERT")

        repository = FailingRepository(self.database)
        service = CustomerRegistrationService(
            repository,
            get_config=lambda key: "5500",
            set_config=lambda key, value: None,
            history_callback=None,
            now=lambda: datetime(2026, 8, 7, 15, 30, 0),
        )
        with self.assertRaisesRegex(RuntimeError, "falha simulada"):
            service.criar(nome="ROLLBACK TESTE", numero_ficha=900, codigo="RB900")
        with closing(sqlite3.connect(self.db_path)) as connection:
            total = connection.execute("SELECT COUNT(*) FROM clientes WHERE codigo='RB900'").fetchone()[0]
        self.assertEqual(total, 0)

    def test_exclusao_ficticios_retorna_quantidade_sem_consulta_count_separada(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executemany(
                "INSERT INTO clientes(numero_ficha,codigo,nome,ficticio) VALUES(?,?,?,1)",
                [(700, "D700", "DEMO 700"), (701, "D701", "DEMO 701")],
            )
            connection.commit()
        maintenance = CustomerMaintenanceRepository(self.database)
        self.assertEqual(maintenance.delete_fictitious(), 2)
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM clientes WHERE ficticio=1").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
