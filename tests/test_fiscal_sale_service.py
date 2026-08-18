import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.fiscal_sale_service import FiscalSaleDraft, FiscalSaleService


class FakeFiscalService:
    TAX_REGIME_CODES = {"SIMPLES_NACIONAL": 1}
    STATE_CODES = {"BA": "29"}

    def __init__(self, db):
        self.db = db
        self.released = []
        self.queued = []

    def connection_factory(self):
        return sqlite3.connect(self.db)

    def load_config(self):
        return {
            "default_model": "65", "environment": "HOMOLOGACAO", "state": "BA",
            "cnpj": "12345678000195", "tax_regime": "SIMPLES_NACIONAL",
            "issuer": {"name": "EMPRESA"}, "sale_series_65": 1,
        }

    def validate_ready(self, **_kwargs):
        return []

    def prepare_sale_items(self, items, **_kwargs):
        return [{"code": "P1", "quantity": 1, "unit_price": 10}] if items else []

    def reserve_number(self, **_kwargs):
        return {"id": "RES-1", "number": 7}

    def release_number(self, reservation_id, **_kwargs):
        self.released.append(reservation_id)

    def build_document_xml(self, **kwargs):
        self.document = kwargs["document"]
        return b"<NFe><infNFe Id='NFe" + b"29" + b"0" * 42 + b"'/></NFe>", "29" + "0" * 42

    def enqueue_transmission(self, **kwargs):
        existing = next((row for row in self.queued if row["access_key"] == kwargs["access_key"]), None)
        if existing:
            return existing
        row = {"id": "QUEUE-1", "status": "PENDENTE", "access_key": kwargs["access_key"]}
        self.queued.append(row)
        return row


class FiscalSaleServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "fiscal-sale.db"
        connection = sqlite3.connect(self.db)
        connection.execute(
            """CREATE TABLE fiscal_sale_documents(
                id INTEGER PRIMARY KEY, sale_id INTEGER UNIQUE, reservation_id TEXT UNIQUE,
                access_key TEXT UNIQUE, model TEXT, environment TEXT, status TEXT,
                xml_b64 TEXT, queue_id TEXT DEFAULT '', protocol TEXT DEFAULT '',
                last_error TEXT DEFAULT '', created_at TEXT, updated_at TEXT)"""
        )
        connection.commit(); connection.close()
        self.fiscal = FakeFiscalService(self.db)
        self.service = FiscalSaleService(self.fiscal)

    def tearDown(self):
        self.temp.cleanup()

    def test_prepara_nfce_com_numero_reservado_e_pagamento_pix(self):
        draft = self.service.prepare(
            items=[{"produto_id": 1}], payments=[{"forma": "PIX", "valor": 10}], actor="caixa"
        )
        self.assertEqual(draft.reservation_id, "RES-1")
        self.assertEqual(draft.model, "65")
        self.assertEqual(self.fiscal.document["number"], 7)
        self.assertEqual(self.fiscal.document["payment_code"], "17")

    def test_falha_na_geracao_libera_numero_reservado(self):
        self.fiscal.build_document_xml = lambda **_kwargs: (_ for _ in ()).throw(ValueError("xml inválido"))
        with self.assertRaisesRegex(ValueError, "xml inválido"):
            self.service.prepare(items=[{"produto_id": 1}], payments=[], actor="caixa")
        self.assertEqual(self.fiscal.released, ["RES-1"])

    def test_rascunho_persistido_e_enfileiramento_repetido_nao_duplica(self):
        draft = FiscalSaleDraft("RES-1", "29" + "0" * 42, "65", "HOMOLOGACAO", b"<NFe/>")
        connection = sqlite3.connect(self.db)
        self.service.persist_draft(connection, 10, draft)
        connection.commit(); connection.close()
        first = self.service.enqueue_pending(sale_id=10, actor="caixa")
        second = self.service.enqueue_pending(sale_id=10, actor="caixa")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.fiscal.queued), 1)
        self.assertEqual(self.service.list_pending()[0]["status"], "ENFILEIRADO")


if __name__ == "__main__":
    unittest.main()
