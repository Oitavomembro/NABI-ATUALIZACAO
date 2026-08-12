from decimal import Decimal
import sqlite3
import tempfile
from pathlib import Path
import unittest

from services.pdv_service import PDVService


class PDVDecimalPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "pdv_decimal.db"
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT)")
        conn.commit()
        conn.close()
        self.service = PDVService(lambda: sqlite3.connect(self.db))

    def tearDown(self):
        self.tmp.cleanup()

    def test_total_desconto_e_troco_preservam_decimal(self):
        total = self.service.totalizar([
            {"qtd": 3, "preco": Decimal("0.10")},
            {"qtd": 1, "preco": Decimal("0.20")},
        ])
        self.assertEqual(total, Decimal("0.50"))
        self.assertIsInstance(total, Decimal)

        calculo = self.service.calcular_finalizacao(
            total,
            desconto=Decimal("10"),
            desconto_tipo="PERCENTUAL",
            recebido=Decimal("1.00"),
            forma="DINHEIRO",
        )
        self.assertEqual(calculo["total_final"], Decimal("0.45"))
        self.assertEqual(calculo["troco"], Decimal("0.55"))
        self.assertTrue(all(isinstance(valor, Decimal) for valor in calculo.values()))

    def test_pagamentos_serializados_sem_float(self):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("BEGIN")
            self.service.registrar_pagamentos_transacao(
                conn,
                11,
                [
                    {"forma": "PIX", "valor": Decimal("0.10")},
                    {"forma": "DINHEIRO", "valor": Decimal("0.20")},
                ],
                total=Decimal("0.30"),
                recebido=Decimal("0.30"),
                troco=Decimal("0.00"),
            )
            conn.commit()
        finally:
            conn.close()

        dados = self.service.obter_pagamentos_venda(11)
        self.assertEqual(dados["total"], Decimal("0.30"))
        self.assertEqual(dados["pagamentos"][0]["valor"], Decimal("0.10"))
        self.assertIsInstance(dados["recebido"], Decimal)

    def test_rateio_fecha_exatamente_total(self):
        itens = [
            {"item": "A", "qtd": 1, "preco": Decimal("0.10"), "subtotal": Decimal("0.10")},
            {"item": "B", "qtd": 1, "preco": Decimal("0.20"), "subtotal": Decimal("0.20")},
        ]
        rateados = self.service.ratear_total_itens(itens, Decimal("0.29"))
        self.assertEqual(sum((item["subtotal"] for item in rateados), Decimal("0")), Decimal("0.29"))
        self.assertTrue(all(isinstance(item["subtotal"], Decimal) for item in rateados))


if __name__ == "__main__":
    unittest.main()
