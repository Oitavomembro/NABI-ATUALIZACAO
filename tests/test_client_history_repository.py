from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import DatabaseManager
from repositories.client_history_repository import ClientHistoryRepository


class ClientHistoryRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "history.db"
        self.database = DatabaseManager(str(self.db_path))
        with self.database.session(write=True) as conn:
            conn.executescript(
                """
                CREATE TABLE clientes (
                    id INTEGER PRIMARY KEY, numero_ficha INTEGER, nome TEXT, limite REAL,
                    saldo_devedor REAL, observacoes TEXT
                );
                CREATE TABLE movimentacoes (
                    id INTEGER PRIMARY KEY, cliente_id INTEGER, tipo TEXT, descricao TEXT,
                    valor REAL, data TEXT, total_parcelas INTEGER
                );
                CREATE TABLE parcelas (
                    id INTEGER PRIMARY KEY, movimentacao_id INTEGER, numero_parcela INTEGER,
                    valor_parcela REAL, vencimento TEXT, status TEXT, valor_pago REAL,
                    data_pagamento TEXT, atraso_registrado INTEGER, dados_confiaveis INTEGER
                );
                CREATE TABLE historico_clientes (
                    id INTEGER PRIMARY KEY, cliente_id INTEGER, evento TEXT, detalhes TEXT, data TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO clientes VALUES (1, 10, 'CLIENTE TESTE', 500, 100, 'OBS')"
            )
            conn.execute(
                "INSERT INTO movimentacoes VALUES (1, 1, 'COMPRA', 'COMPRA 1', 100, '01/01/2024', 2)"
            )
            conn.execute(
                "INSERT INTO parcelas VALUES (1, 1, 1, 50, '10/01/2024', 'PAGO', 50, '12/01/2024', 0, 1)"
            )
            conn.execute(
                "INSERT INTO parcelas VALUES (2, 1, 2, 50, '10/02/2024', 'PENDENTE', 0, '', 0, 1)"
            )
            conn.execute(
                "INSERT INTO historico_clientes VALUES (1, 1, 'CADASTRO', 'CRIADO', '01/01/2024')"
            )
        self.repository = ClientHistoryRepository(self.database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_load_returns_consolidated_history(self) -> None:
        data = self.repository.load(1)
        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(data.client[1], 'CLIENTE TESTE')
        self.assertEqual(len(data.transactions), 1)
        self.assertEqual(len(data.events), 1)
        self.assertEqual(data.purchase_summary['total_compras'], 1)
        self.assertEqual(data.purchase_summary['pagas_atraso'], 1)
        self.assertEqual(data.purchase_summary['vencidas_aberto'], 1)
        self.assertIsInstance(data.purchase_summary['compras'][0]['valor'], Decimal)
        self.assertIsInstance(data.purchase_summary['compras'][0]['parcelas'][0]['valor'], Decimal)

    def test_missing_client_returns_none(self) -> None:
        self.assertIsNone(self.repository.load(999))

    def test_invalid_client_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.load(0)

    def test_parse_date_accepts_supported_formats(self) -> None:
        self.assertIsNotNone(self.repository.parse_date('2024-01-01'))
        self.assertIsNotNone(self.repository.parse_date('01/01/2024 10:30:00'))
        self.assertIsNone(self.repository.parse_date('invalid'))


if __name__ == '__main__':
    unittest.main()
