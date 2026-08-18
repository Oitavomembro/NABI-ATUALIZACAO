import sqlite3
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace
from pathlib import Path

from services.fiscal_sale_service import FiscalSaleDraft, FiscalSaleService
from services.fiscal_service import FiscalService


class FakeFiscalService:
    TAX_REGIME_CODES = {"SIMPLES_NACIONAL": 1}
    STATE_CODES = {"BA": "29"}
    _normalize_tax_document = staticmethod(FiscalService._normalize_tax_document)
    _is_valid_cnpj = staticmethod(FiscalService._is_valid_cnpj)
    _is_valid_cpf = staticmethod(FiscalService._is_valid_cpf)

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

    def cancel_transmission(self, queue_id, **_kwargs):
        row = next(item for item in self.queued if item["id"] == queue_id)
        row["status"] = "CANCELADO"
        return row

    def send_event(self, **_kwargs):
        return SimpleNamespace(success=True, protocol="PROTO-CANCEL", status_code="135", message="Evento registrado"), {"event": "CANCELAMENTO"}

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
        connection.execute(
            """CREATE TABLE clientes(
                id INTEGER PRIMARY KEY,codigo TEXT,nome TEXT,cpf TEXT,email TEXT,
                inscricao_estadual TEXT,contribuinte_icms INTEGER,
                fiscal_logradouro TEXT,fiscal_numero TEXT,fiscal_bairro TEXT,
                fiscal_codigo_municipio TEXT,fiscal_municipio TEXT,fiscal_uf TEXT,fiscal_cep TEXT)"""
        )
        connection.execute(
            """INSERT INTO clientes VALUES(
                1,'CLI1','CLIENTE VÁLIDO','52998224725','cliente@example.com','',0,
                'RUA A','10','CENTRO','3550308','SÃO PAULO','SP','01001000')"""
        )
        connection.execute(
            "INSERT INTO clientes(id,codigo,nome,cpf) VALUES(2,'CONSUMIDOR_FINAL','CONSUMIDOR FINAL','')"
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

    def test_cartao_pos_aceita_autorizacao_opcional(self):
        self.service.prepare(
            items=[{"produto_id": 1}],
            payments=[{"forma": "CREDITO", "valor": 10, "card_integration": 2,
                       "card_authorization": "NSU123"}],
            actor="caixa",
        )
        self.assertEqual(self.fiscal.document["payment_code"], "03")
        self.assertEqual(
            self.fiscal.document["payment_detail"],
            {"integration": 2, "authorization": "NSU123"},
        )

    def test_pagamentos_mistos_sao_preservados_individualmente(self):
        self.service.prepare(
            items=[{"produto_id": 1}],
            payments=[
                {"forma": "PIX", "valor": "4.00"},
                {"forma": "CREDIARIO", "valor": "6.00"},
            ],
            actor="caixa",
        )
        self.assertEqual(
            self.fiscal.document["payments"],
            [
                {"code": "17", "amount": Decimal("4.00")},
                {"code": "05", "amount": Decimal("6.00")},
            ],
        )

    def test_falha_na_geracao_libera_numero_reservado(self):
        self.fiscal.build_document_xml = lambda **_kwargs: (_ for _ in ()).throw(ValueError("xml inválido"))
        with self.assertRaisesRegex(ValueError, "xml inválido"):
            self.service.prepare(
                items=[{"produto_id": 1}], payments=[{"forma": "PIX", "valor": 10}], actor="caixa"
            )
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
        self.assertEqual(
            self.service.summary(),
            {"total": 1, "authorized": 0, "pending": 1, "failed": 0},
        )

    def test_destinatario_e_destino_sao_obtidos_do_cliente(self):
        recipient, destination = self.service.recipient_for_customer(1, model="55")
        self.assertEqual(recipient["document"], "52998224725")
        self.assertEqual(recipient["city_code"], "3550308")
        self.assertEqual(recipient["state"], "SP")
        self.assertEqual(destination, 2)

    def test_consumidor_final_na_nfce_nao_exige_documento(self):
        recipient, destination = self.service.recipient_for_customer(2, model="65")
        self.assertEqual(recipient, {})
        self.assertEqual(destination, 1)

    def test_cancelamento_pendente_cancela_fila_e_libera_numero(self):
        draft = FiscalSaleDraft("RES-1", "29" + "0" * 42, "65", "HOMOLOGACAO", b"<NFe/>")
        connection = sqlite3.connect(self.db)
        self.service.persist_draft(connection, 20, draft)
        connection.commit(); connection.close()
        self.service.enqueue_pending(sale_id=20, actor="caixa")
        connection = sqlite3.connect(self.db)
        self.service.prepare_local_cancellation(connection, 20)
        connection.commit(); connection.close()
        self.service.finalize_local_cancellation(sale_id=20, actor="caixa")
        connection = sqlite3.connect(self.db)
        status = connection.execute("SELECT status FROM fiscal_sale_documents WHERE sale_id=20").fetchone()[0]
        connection.close()
        self.assertEqual(status, "CANCELADO")
        self.assertEqual(self.fiscal.queued[0]["status"], "CANCELADO")
        self.assertEqual(self.fiscal.released, ["RES-1"])

    def test_cancelamento_local_bloqueia_documento_autorizado(self):
        draft = FiscalSaleDraft("RES-2", "29" + "1" * 42, "65", "HOMOLOGACAO", b"<NFe/>")
        connection = sqlite3.connect(self.db)
        self.service.persist_draft(connection, 21, draft)
        connection.execute("UPDATE fiscal_sale_documents SET status='AUTORIZADO',protocol='P1' WHERE sale_id=21")
        connection.commit()
        with self.assertRaisesRegex(ValueError, "Central Fiscal"):
            self.service.prepare_local_cancellation(connection, 21)
        connection.close()

    def test_cancelamento_autorizado_registra_evento_antes_da_reversao(self):
        draft = FiscalSaleDraft("RES-3", "29" + "2" * 42, "65", "HOMOLOGACAO", b"<NFe/>")
        connection = sqlite3.connect(self.db)
        self.service.persist_draft(connection, 22, draft)
        connection.execute("UPDATE fiscal_sale_documents SET status='AUTORIZADO',protocol='P2' WHERE sale_id=22")
        connection.commit(); connection.close()
        event = self.service.cancel_authorized(
            sale_id=22, password="senha", actor="gerente",
            justification="Cancelamento solicitado corretamente.",
        )
        self.assertEqual(event["event"], "CANCELAMENTO")
        connection = sqlite3.connect(self.db)
        status = connection.execute("SELECT status FROM fiscal_sale_documents WHERE sale_id=22").fetchone()[0]
        connection.close()
        self.assertEqual(status, "CANCELADO_FISCAL")


if __name__ == "__main__":
    unittest.main()
