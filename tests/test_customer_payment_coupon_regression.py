from pathlib import Path
import tempfile
import sqlite3
import unittest

from database import DatabaseManager
from services.receipt_service import ReceiptService


class CustomerPaymentCouponRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "db.sqlite"
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
        CREATE TABLE clientes(
            id INTEGER PRIMARY KEY, nome TEXT, codigo TEXT, numero_ficha INTEGER,
            telefone TEXT, endereco TEXT, saldo_devedor REAL
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
        INSERT INTO clientes VALUES(1,'Cliente Teste','C1',5501,'','',150);
        INSERT INTO movimentacoes VALUES
          (10,1,'COMPRA','Guarda-roupa',300,'01/08/2026','01/09/2026','PARCIAL',3,150,'',''),
          (20,1,'PAGAMENTO','Pagamento recebido via PIX',100,'05/08/2026 08:30:00',NULL,'PAGO',1,0,'PIX','Caixa');
        INSERT INTO parcelas VALUES
          (1,10,1,100,'01/09/2026','PAGO',100,'05/08/2026'),
          (2,10,2,100,'01/10/2026','PENDENTE',0,''),
          (3,10,3,100,'01/11/2026','PENDENTE',0,'');
        """)
        conn.commit()
        conn.close()
        self.manager = DatabaseManager(self.db_path)
        self.service = ReceiptService(
            self.manager,
            config_getter=lambda key: {"nome_loja": "NabiCode"}.get(key, ""),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_payment_coupon_contains_sale_and_installments(self):
        text = self.service.build_payment_text(20, [{
            "venda_id": 10,
            "valor_aplicado": 100,
            "saldo_antes": 250,
            "saldo_depois": 150,
        }])
        self.assertIn("RECIBO DE PAGAMENTO", text)
        self.assertIn("Cliente Teste", text)
        self.assertIn("Venda #10", text)
        self.assertIn("Parcelas: 3", text)
        self.assertIn("P2: venc 01/10/2026", text)
        self.assertIn("VALOR RECEBIDO: R$ 100.00", text)

    def test_source_does_not_generate_pdf_automatically_after_payment(self):
        source = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")
        payment_block_start = source.index("def receber_pagamento_cliente")
        payment_block_end = source.index("def abrir_historico_cliente_selecionado", payment_block_start)
        payment_block = source[payment_block_start:payment_block_end]
        self.assertIn("janela_recibo_pagamento_cliente", payment_block)
        self.assertNotIn("gerar_pdf_pagamento_cliente(\n                    pagamento_mov_id", payment_block)
        self.assertIn('text="Salvar PDF (opcional)"', source)


if __name__ == "__main__":
    unittest.main()
