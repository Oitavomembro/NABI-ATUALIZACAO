from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from database import DatabaseManager
from services.receipt_service import ReceiptService


class ReceiptServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "receipt.db"
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT, codigo TEXT, numero_ficha INTEGER, telefone TEXT, endereco TEXT)"
            )
            connection.execute(
                "INSERT INTO clientes VALUES (1, 'CLIENTE TESTE', 'C001', 12, '75999990000', 'RUA A')"
            )
            connection.commit()
        finally:
            connection.close()
        config = {"nome_loja": "LOJA TESTE", "rodape_cupom": "OBRIGADO"}
        self.service = ReceiptService(
            DatabaseManager(self.db_path),
            config_getter=lambda key: config.get(key, ""),
            now=lambda: datetime(2026, 8, 2, 21, 30, 0),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_builds_sale_receipt(self) -> None:
        text = self.service.build_sale_text(
            1,
            [{"item": "PRODUTO", "qtd": 2, "preco": 5.0, "subtotal": 10.0}],
            10.0,
            "VENDA",
        )
        self.assertIn("LOJA TESTE", text)
        self.assertIn("CLIENTE TESTE", text)
        self.assertIn("TOTAL: R$ 10.00", text)
        self.assertIn("OBRIGADO", text)

    def test_delivery_includes_contact_data(self) -> None:
        text = self.service.build_sale_text(
            1,
            [{"item": "PRODUTO", "qtd": 1, "preco": 3.0, "subtotal": 3.0}],
            3.0,
            "ENTREGA",
        )
        self.assertIn("Telefone: 75999990000", text)
        self.assertIn("Endereço: RUA A", text)

    def test_rejects_total_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            self.service.build_sale_text(
                1,
                [{"item": "PRODUTO", "qtd": 1, "preco": 3.0, "subtotal": 3.0}],
                4.0,
                "VENDA",
            )

    def test_rejects_missing_customer(self) -> None:
        with self.assertRaisesRegex(ValueError, "não encontrado"):
            self.service.build_sale_text(
                999,
                [{"item": "PRODUTO", "qtd": 1, "preco": 3.0, "subtotal": 3.0}],
                3.0,
                "VENDA",
            )


if __name__ == "__main__":
    unittest.main()
