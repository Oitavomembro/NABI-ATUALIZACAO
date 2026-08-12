from pathlib import Path
import tempfile
import sqlite3
import unittest

from services.pdf_document_service import PDFDocumentService


class CustomerPaymentReceiptRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "db.sqlite"
        conn = sqlite3.connect(self.db)
        conn.executescript("""
        CREATE TABLE clientes(
            id INTEGER PRIMARY KEY, nome TEXT, codigo TEXT, numero_ficha INTEGER,
            telefone TEXT, endereco TEXT, referencia TEXT, saldo_devedor REAL
        );
        CREATE TABLE movimentacoes(
            id INTEGER PRIMARY KEY, cliente_id INTEGER, tipo TEXT, descricao TEXT,
            valor REAL, data TEXT, vencimento TEXT, status_pagamento TEXT,
            total_parcelas INTEGER, valor_aberto REAL, forma_pagamento TEXT,
            responsavel TEXT
        );
        CREATE TABLE parcelas(
            id INTEGER PRIMARY KEY, movimentacao_id INTEGER, numero_parcela INTEGER,
            valor_parcela REAL, vencimento TEXT, status TEXT, valor_pago REAL,
            data_pagamento TEXT
        );
        INSERT INTO clientes VALUES(1,'Cliente Teste','C1',5501,'','','',150);
        INSERT INTO movimentacoes VALUES
            (10,1,'COMPRA','2x Produto',300,'01/08/2026','01/09/2026','PARCIAL',3,150,'',''),
            (20,1,'PAGAMENTO','Pagamento recebido via PIX',100,'05/08/2026 08:30:00',NULL,'PAGO',1,0,'PIX','Caixa');
        INSERT INTO parcelas VALUES
            (1,10,1,100,'01/09/2026','PAGO',100,'05/08/2026'),
            (2,10,2,100,'01/10/2026','PENDENTE',0,''),
            (3,10,3,100,'01/11/2026','PENDENTE',0,'');
        """)
        conn.commit()
        conn.close()
        self.service = PDFDocumentService(
            connection_factory=lambda: sqlite3.connect(self.db),
            config_getter=lambda key: {
                "nome_loja": "NabiCode",
                "modelo_recibo": "A4",
                "impressao_fonte": "Helvetica",
                "impressao_fonte_tamanho": "10",
                "impressao_margem_mm": "7",
                "impressao_qrcode": "0",
                "impressao_mostrar_assinatura": "0",
            }.get(key, ""),
            pdf_dir=Path(self.temp.name) / "pdf",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_generates_detailed_customer_payment_receipt(self):
        path = self.service.generate_customer_payment(
            20,
            allocations=[{
                "venda_id": 10,
                "valor_aplicado": 100,
                "saldo_antes": 250,
                "saldo_depois": 150,
            }],
        )
        self.assertTrue(Path(path).exists())
        self.assertGreater(Path(path).stat().st_size, 500)

    def test_missing_payment_raises_clear_error(self):
        with self.assertRaisesRegex(RuntimeError, "Pagamento não encontrado"):
            self.service.generate_customer_payment(999, allocations=[])


if __name__ == "__main__":
    unittest.main()
