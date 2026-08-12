from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.pdf_document_service import PDFDocumentService


class PDFDocumentServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "test.db"
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY, nome TEXT, codigo TEXT, numero_ficha TEXT,
                telefone TEXT, endereco TEXT, referencia TEXT, saldo_devedor REAL
            );
            CREATE TABLE movimentacoes (
                id INTEGER PRIMARY KEY, tipo TEXT, descricao TEXT, valor REAL, data TEXT,
                forma_pagamento TEXT, responsavel TEXT, cliente_id INTEGER
            );
            INSERT INTO clientes VALUES (1,'CLIENTE TESTE','C1','10','9999','RUA A','PORTAO AZUL',25.5);
            INSERT INTO movimentacoes VALUES (7,'RECEBIMENTO','Parcela',80,'2026-08-02','PIX','ANA',1);
            """
        )
        connection.commit()
        connection.close()
        self.config = {
            "nome_loja": "LOJA TESTE", "modelo_recibo": "A4", "modelo_entrega": "A4",
            "modelo_fechamento": "A4", "impressao_qrcode": "0", "impressao_mostrar_assinatura": "0",
        }
        self.registered = []
        self.service = PDFDocumentService(
            connection_factory=lambda: sqlite3.connect(self.db),
            config_getter=lambda key: self.config.get(key, ""),
            pdf_dir=self.root / "pdfs",
            document_registrar=lambda *args: self.registered.append(args),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_safe_name_and_default_model(self):
        self.assertEqual("Joao_da_Silva", self.service.safe_name("João da Silva"))
        self.assertEqual("A4", self.service.document_model("entrega"))
        self.assertEqual("A4", self.service.document_model("recibo_desconhecido"))

    def test_config_bool_accepts_legacy_and_text_values(self):
        self.config["flag"] = "sim"
        self.assertTrue(self.service.config_bool("flag", False))
        self.config["flag"] = "false"
        self.assertFalse(self.service.config_bool("flag", True))
        self.assertTrue(self.service.config_bool("missing", True))

    def test_thermal_height_estimate_grows_with_wrapped_content(self):
        customer = self.service._customer(1)
        short = self.service._estimate_sale_height_mm(
            model="Térmica 58 mm econômica",
            items=[{"qtd": 1, "item": "ITEM", "preco": 10, "subtotal": 10}],
            document_type="VENDA",
            customer=customer,
            footer="",
            payment_plan=None,
        )
        long = self.service._estimate_sale_height_mm(
            model="Térmica 58 mm econômica",
            items=[{
                "qtd": 1,
                "item": "DESCRIÇÃO MUITO LONGA " * 12,
                "preco": 10,
                "subtotal": 10,
            }],
            document_type="ENTREGA",
            customer=customer,
            footer="RODAPÉ EXTENSO " * 20,
            payment_plan={
                "parcelas": [
                    {"numero": number, "valor": 10, "vencimento": "2026-08-10"}
                    for number in range(1, 8)
                ]
            },
        )
        self.assertGreater(long, short)

    def test_generate_sale_creates_pdf_and_registers_document(self):
        path = self.service.generate_sale(
            1,
            [{"qtd": 2, "item": "PRODUTO", "preco": 10.0, "subtotal": 20.0}],
            20.0,
            "VENDA",
            document_id=99,
        )
        self.assertTrue(Path(path).is_file())
        self.assertGreater(Path(path).stat().st_size, 100)
        self.assertEqual(99, self.registered[0][0])

    def test_generate_movement_closes_connection_and_creates_pdf(self):
        path = self.service.generate_movement(7)
        self.assertTrue(Path(path).is_file())
        self.assertEqual("movimento", self.registered[0][1])

    def test_generate_closing_creates_pdf(self):
        summary = {
            "data": "2026-08-02", "abertura": 100.0, "vendas": 50.0, "recebimentos": 10.0,
            "suprimentos": 0.0, "retiradas": 5.0, "contas": 0.0, "entradas": 160.0,
            "saidas": 5.0, "saldo_esperado": 155.0, "formas": {"PIX": 10.0},
        }
        path = self.service.generate_closing(summary, counted_value=155.0, responsible="ANA")
        self.assertTrue(Path(path).is_file())


if __name__ == "__main__":
    unittest.main()
