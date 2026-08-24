from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
import sqlite3

import pytest

from assistant_nabi import (
    AssistantActor, CapabilityLevel, DraftConfirmationService,
    NabiCodeProcurementAssistantGateway, PurchaseOrderDraftService,
    PurchaseOrderItemRequest, SupplierRegistrationDraftService,
)
from administration.purchase_management_service import PurchaseManagementService
from database import DatabaseManager
from repositories import FornecedorRepository


class Purchases:
    def __init__(self):
        self.suppliers = (SimpleNamespace(
            supplier_id=3, name="Fornecedor Real", active=True,
        ),)
        self.products = (SimpleNamespace(
            product_id=5, code="P5", description="Café",
            unit_cost=Decimal("8.50"), current_stock=Decimal("10"),
        ),)
        self.calls = []

    def list_suppliers(self): return self.suppliers
    def list_products(self, supplier_id=None): return self.products
    def create_supplier_assisted(self, *args, **kwargs):
        self.calls.append(("supplier", args, kwargs)); return 11
    def create_order_assisted(self, *args, **kwargs):
        self.calls.append(("order", args, kwargs)); return 21


def _authorization(draft):
    broker = DraftConfirmationService()
    actor = AssistantActor("operador", "OPERADOR", "sessao-real")
    challenge = broker.issue(draft, actor=actor)
    assert challenge.required_capability is CapabilityLevel.REINFORCED_CONFIRMATION
    return broker.confirm(token=challenge.token, draft=draft, actor=actor)


def test_fornecedor_e_rascunho_imutavel_sem_persistencia():
    purchases = Purchases()
    draft = SupplierRegistrationDraftService().create(
        name=" Fornecedor  Real ", legal_name="Empresa Real Ltda",
        document="123", phone="71999999999", email="compras@example.com",
    )
    assert draft.name == "Fornecedor Real" and len(draft.fingerprint) == 64
    assert purchases.calls == []
    with pytest.raises(Exception):
        draft.name = "alterado"


def test_pedido_resolve_ids_reais_calcula_previa_e_nao_persiste():
    purchases = Purchases()
    draft = PurchaseOrderDraftService(purchases).create(
        3, (PurchaseOrderItemRequest(5, "2", "8.50"),), notes="Reposição",
    )
    assert draft.supplier_id == 3 and draft.items[0].product_id == 5
    assert draft.total == Decimal("17.00") and purchases.calls == []
    with pytest.raises(ValueError, match="não encontrado"):
        PurchaseOrderDraftService(purchases).create(
            3, (PurchaseOrderItemRequest(99, "1", "1"),)
        )
    with pytest.raises(ValueError, match="mais de uma vez"):
        PurchaseOrderDraftService(purchases).create(3, (
            PurchaseOrderItemRequest(5, "1", "1"),
            PurchaseOrderItemRequest(5, "1", "1"),
        ))
    with pytest.raises(ValueError, match="texto decimal"):
        PurchaseOrderItemRequest(5, 1.0, "1")


def test_gateway_exige_confirmacao_e_transporta_usuario_e_idempotencia():
    purchases = Purchases()
    gateway = NabiCodeProcurementAssistantGateway(purchases)
    supplier = SupplierRegistrationDraftService().create(name="Fornecedor")
    assert gateway.execute_supplier(supplier, _authorization(supplier)) == 11
    call = purchases.calls[-1][2]
    assert call["expected_username"] == "operador"
    assert call["idempotency_key"] == f"nabi:supplier:{supplier.draft_id}"

    order = PurchaseOrderDraftService(purchases).create(
        3, (PurchaseOrderItemRequest(5, "2", "8.50"),)
    )
    authorization = _authorization(order)
    assert gateway.execute_order(order, authorization) == 21
    assert purchases.calls[-1][2]["idempotency_key"] == f"nabi:purchase-order:{order.draft_id}"
    with pytest.raises(PermissionError, match="já foi utilizada"):
        gateway.execute_order(order, authorization)


def test_gateway_recusa_autorizacao_fabricada_sem_mutar():
    purchases = Purchases()
    draft = SupplierRegistrationDraftService().create(name="Fornecedor")
    with pytest.raises(PermissionError, match="broker"):
        NabiCodeProcurementAssistantGateway(purchases).execute_supplier(
            draft, SimpleNamespace(fingerprint=draft.fingerprint)
        )
    assert purchases.calls == []


def test_fornecedor_assistido_journal_e_cadastro_sao_atomicos(tmp_path):
    path = tmp_path / "supplier.db"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE fornecedores(
          id INTEGER PRIMARY KEY AUTOINCREMENT,razao_social TEXT,nome_fantasia TEXT,
          cnpj TEXT,telefone TEXT,email TEXT,ativo INTEGER,criado_em TEXT,atualizado_em TEXT);
        CREATE TABLE assistant_operation_journal(
          id INTEGER PRIMARY KEY AUTOINCREMENT,idempotency_key TEXT UNIQUE,
          operation_kind TEXT,fingerprint TEXT,status TEXT,result_json TEXT,
          username TEXT,created_at TEXT,committed_at TEXT DEFAULT '');
        CREATE TABLE auditoria(
          id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,usuario TEXT,modulo TEXT,
          acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
    """)
    connection.commit(); connection.close()
    database = DatabaseManager(path)
    purchase = SimpleNamespace(database=database, repository=Mock())
    security = Mock()
    security.session = SimpleNamespace(user=SimpleNamespace(username="operador"))
    security.is_expired.return_value = False
    security.require.return_value = True
    service = PurchaseManagementService(purchase, FornecedorRepository(database), security)
    kwargs = dict(
        legal_name="Empresa", document="123", phone="71", email="a@b.com",
        expected_username="operador", idempotency_key="nabi:supplier:d1",
        operation_fingerprint="a" * 64,
    )
    first = service.create_supplier_assisted("Fornecedor", **kwargs)
    assert service.create_supplier_assisted("Fornecedor", **kwargs) == first
    assert database.fetch_one("SELECT COUNT(*) AS total FROM fornecedores")["total"] == 1
    row = database.fetch_one(
        "SELECT operation_kind,status,username FROM assistant_operation_journal"
    )
    assert tuple(row) == ("SUPPLIER_CREATE", "COMMITTED", "operador")
    with pytest.raises(PermissionError, match="outro conteúdo"):
        service.create_supplier_assisted(
            "Outro", **{**kwargs, "operation_fingerprint": "b" * 64}
        )


def test_fornecedor_assistido_reverte_journal_se_cadastro_falhar(tmp_path):
    path = tmp_path / "rollback.db"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE fornecedores(
          id INTEGER PRIMARY KEY AUTOINCREMENT,razao_social TEXT,nome_fantasia TEXT,
          cnpj TEXT,telefone TEXT,email TEXT,ativo INTEGER,criado_em TEXT,atualizado_em TEXT);
        CREATE TRIGGER falha_fornecedor BEFORE INSERT ON fornecedores
          BEGIN SELECT RAISE(ABORT, 'falha'); END;
        CREATE TABLE assistant_operation_journal(
          id INTEGER PRIMARY KEY AUTOINCREMENT,idempotency_key TEXT UNIQUE,
          operation_kind TEXT,fingerprint TEXT,status TEXT,result_json TEXT,
          username TEXT,created_at TEXT,committed_at TEXT DEFAULT '');
        CREATE TABLE auditoria(
          id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,usuario TEXT,modulo TEXT,
          acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
    """)
    connection.commit(); connection.close()
    database = DatabaseManager(path)
    security = Mock()
    security.session = SimpleNamespace(user=SimpleNamespace(username="operador"))
    security.is_expired.return_value = False; security.require.return_value = True
    service = PurchaseManagementService(
        SimpleNamespace(database=database, repository=Mock()),
        FornecedorRepository(database), security,
    )
    with pytest.raises(sqlite3.IntegrityError):
        service.create_supplier_assisted(
            "Fornecedor", expected_username="operador",
            idempotency_key="nabi:supplier:failed", operation_fingerprint="c" * 64,
        )
    assert database.fetch_one("SELECT 1 FROM assistant_operation_journal") is None
