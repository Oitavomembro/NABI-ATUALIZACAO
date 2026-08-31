from __future__ import annotations

import sqlite3
import tempfile
import unittest
from unittest.mock import patch
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
            INSERT INTO clientes VALUES (2,'CONSUMIDOR FINAL','CONSUMIDOR_FINAL',NULL,'','','',0);
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

    def test_condicoes_estimadas_recusadas_em_comprovante_de_venda(self):
        with self.assertRaisesRegex(ValueError, "exclusivas de orçamento"):
            self.service.generate_sale(1, [], 10, "VENDA", budget_terms="simulação")

    def test_budget_terms_fit_paper_and_do_not_show_existing_debt(self):
        from reportlab.pdfbase.pdfmetrics import stringWidth

        for model in ("A4", "Térmica 80 mm"):
            with self.subTest(model=model):
                self.config["modelo_recibo"] = model
                drawn = []
                create_canvas = self.service._create_canvas

                def recording_canvas(*args):
                    canvas, page, mm = create_canvas(*args)
                    for method, centered in (("drawString", False), ("drawCentredString", True)):
                        original = getattr(canvas, method)

                        def record(x, y, text, *extra, original=original, centered=centered, **kwargs):
                            length = stringWidth(text, canvas._fontname, canvas._fontsize)
                            left = x - length / 2 if centered else x
                            self.assertGreaterEqual(left, 0)
                            self.assertLessEqual(left + length, page[0] + 0.01)
                            self.assertGreater(y, 0)
                            drawn.append(text)
                            return original(x, y, text, *extra, **kwargs)

                        setattr(canvas, method, record)
                    return canvas, page, mm

                with patch.object(self.service, "_create_canvas", side_effect=recording_canvas):
                    self.service.generate_sale(
                        1, [{"qtd": 2, "item": "PRODUTO", "preco": 50, "subtotal": 100}],
                        100, "ORCAMENTO", budget_terms=(
                            "CONDIÇÃO ESTIMADA (NÃO É RECEBIMENTO)\n"
                            "Forma: CREDIÁRIO\nEntrada: R$ 10,00\nSaldo estimado: R$ 90,00 em 3x"
                        ),
                    )
                text = " ".join(drawn)
                self.assertIn("NÃO É RECEBIMENTO", text)
                self.assertIn("SEM VALOR FISCAL", text)
                self.assertIn("90,00 em 3x", text)
                self.assertNotIn("Saldo atual da ficha", text)
                self.assertEqual([], self.registered)

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

    def test_consumidor_final_e_identificado_sem_dados_de_ficha(self):
        customer = self.service._customer(2)
        self.assertTrue(self.service._is_final_consumer(
            name=customer[0], code=customer[1], record=customer[2],
        ))
        self.assertFalse(self.service._is_final_consumer(
            name="CLIENTE TESTE", code="C1", record="10",
        ))

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
