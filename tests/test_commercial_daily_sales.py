from __future__ import annotations

import unittest
from decimal import Decimal

from commercial.infrastructure.daily_sales_gateway import NabiCodeDailySalesGateway


class _Transactions:
    def __init__(self, rows):
        self.rows = list(rows)
        self.cancelled = []

    def list_sales_for_day(self):
        return [dict(row) for row in self.rows]

    def cancel_sale(self, sale_id, *, user):
        self.cancelled.append((sale_id, user))


class _Receipts:
    def __init__(self):
        self.calls = []

    def build_sale_text(self, customer_id, items, total, kind, sale_id=None):
        self.calls.append((customer_id, items, total, kind, sale_id))
        return f"VENDA {sale_id}"


class _Printing:
    def __init__(self):
        self.calls = []

    def print_text(self, text, **options):
        self.calls.append((text, options))
        return "Impressora"


class _Pdf:
    def __init__(self):
        self.calls = []

    def generate_sale(self, customer_id, items, total, kind, document_id=None):
        self.calls.append((customer_id, items, total, kind, document_id))
        return "C:/teste/venda.pdf"


class _Opener:
    def __init__(self):
        self.paths = []

    def open(self, path):
        self.paths.append(path)
        return path


class DailySalesGatewayTests(unittest.TestCase):
    def setUp(self):
        self.transactions = _Transactions([{
            "id": 41, "cliente_id": 7,
            "descricao": "2x Café (R$ 10.00) | 1x Leite [AVULSO/SEM ESTOQUE] (R$ 5.00)",
            "valor": Decimal("15.00"), "data": "2026-08-23 10:30:00",
            "status_pagamento": "PAGO", "fiscal_status": "",
        }])
        self.receipts = _Receipts()
        self.printing = _Printing()
        self.pdf = _Pdf()
        self.opener = _Opener()
        self.gateway = NabiCodeDailySalesGateway(
            transaction_service=self.transactions, receipts=self.receipts,
            printing=self.printing, pdf=self.pdf, opener=self.opener,
        )

    def test_lista_estado_real_e_reconstroi_segunda_via(self):
        sale = self.gateway.list_today()[0]
        self.assertEqual((sale.sale_id, sale.customer_id, sale.total), (41, 7, Decimal("15.00")))
        self.assertEqual(self.gateway.preview_text(sale), "VENDA 41")
        items = self.receipts.calls[0][1]
        self.assertEqual([item["subtotal"] for item in items], [Decimal("10.00"), Decimal("5.00")])
        self.assertEqual(self.gateway.print_thermal(sale), "Impressora")
        self.assertEqual(self.gateway.generate_pdf(sale), "C:/teste/venda.pdf")
        self.assertEqual(self.gateway.open_file("C:/teste/venda.pdf"), "C:/teste/venda.pdf")

    def test_cancelamento_local_delega_uma_vez(self):
        self.gateway.cancel_local(41, user="operador")
        self.assertEqual(self.transactions.cancelled, [(41, "operador")])

    def test_cancelamento_fiscal_e_bloqueado_sem_chamar_backend(self):
        self.transactions.rows[0]["fiscal_status"] = "AUTORIZADO"
        with self.assertRaisesRegex(ValueError, "Central Fiscal"):
            self.gateway.cancel_local(41, user="operador")
        self.assertEqual(self.transactions.cancelled, [])

    def test_cancelada_nao_e_cancelada_novamente(self):
        self.transactions.rows[0]["status_pagamento"] = "CANCELADO"
        with self.assertRaisesRegex(ValueError, "já está cancelada"):
            self.gateway.cancel_local(41, user="operador")
        self.assertEqual(self.transactions.cancelled, [])


if __name__ == "__main__":
    unittest.main()
