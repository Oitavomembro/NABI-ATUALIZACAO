from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest

from administration.product_management_service import ProductManagementService
from assistant_nabi import (
    AssistantActor, DraftConfirmationService, NabiCodeProductStockAssistantGateway,
    ProductStockDraftService,
)
from commercial.application.product_dto import ProductCreateCommand, ProductDetails
from services.assisted_product_stock_service import AssistedProductStockService


class DraftProducts:
    def __init__(self, stock="5"):
        self.product = ProductDetails(7, "P7", "", "CAFÉ", "10", "4", stock, "1", False, "MERCADORIA", True)
    def get_product(self, product_id):
        if product_id != 7: raise ValueError("Produto não encontrado.")
        return self.product


def test_drafts_sao_imutaveis_deterministicos_e_bloqueiam_negativo():
    service = ProductStockDraftService(DraftProducts())
    first = service.create_product(description="Café", sale_price="10", minimum_stock="2")
    second = service.create_product(description="Café", sale_price="10", minimum_stock="2")
    assert first.fingerprint == second.fingerprint
    assert first.current_stock == 0 and first.operation_kind == "PRODUCT_CREATE"
    with pytest.raises(Exception):
        first.description = "alterado"
    removal = service.create_stock(operation="STOCK_REMOVE", product_id=7, value="2", reason="AVARIA")
    assert removal.previous_balance == Decimal("5.0000")
    assert removal.new_balance == Decimal("3.0000")
    with pytest.raises(ValueError, match="negativo"):
        service.create_stock(operation="STOCK_REMOVE", product_id=7, value="6", reason="AVARIA")
    with pytest.raises(ValueError, match="negativo"):
        service.create_stock(operation="STOCK_ADJUST", product_id=7, value="-1", reason="CONTAGEM")


class MemoryDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("""CREATE TABLE assistant_operation_journal(
          idempotency_key TEXT PRIMARY KEY,operation_kind TEXT,fingerprint TEXT,status TEXT,
          result_json TEXT,username TEXT,created_at TEXT,committed_at TEXT)""")
        self.connection.execute("CREATE TABLE effects(kind TEXT, value TEXT)")
    @contextmanager
    def session(self, write=False):
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise


class FakeProductBackend:
    def __init__(self, database):
        self.produtos = SimpleNamespace(database=database)
        self.fail = False
    def salvar(self, **kwargs):
        connection = kwargs["connection"]
        connection.execute("INSERT INTO effects VALUES('PRODUCT',?)", (kwargs["nome"],))
        if self.fail: raise RuntimeError("falha")
        return 11


class FakeStockBackend:
    def __init__(self, database): self.database = database
    def movimentar_na_transacao(self, connection, product_id, amount, **kwargs):
        connection.execute("INSERT INTO effects VALUES('STOCK',?)", (str(amount),))
        return SimpleNamespace(movimentacao_id=21, produto_id=product_id, tipo="ENTRADA",
                               quantidade=amount, saldo_anterior=5, saldo_atual=Decimal("5") + Decimal(str(amount)))
    def ajustar_na_transacao(self, connection, product_id, balance, **kwargs):
        connection.execute("INSERT INTO effects VALUES('ADJUST',?)", (str(balance),))
        return SimpleNamespace(movimentacao_id=22, produto_id=product_id, tipo="AJUSTE",
                               quantidade=Decimal(balance)-5, saldo_anterior=5, saldo_atual=balance)


def test_servico_atomico_reexecuta_sem_duplicar_e_rejeita_fingerprint_divergente():
    database = MemoryDatabase(); products = FakeProductBackend(database); stock = FakeStockBackend(database)
    service = AssistedProductStockService(products, stock)
    command = ProductCreateCommand("", "CAFÉ", Decimal("10"))
    assert service.create_product(command, username="maria", idempotency_key="k1", operation_fingerprint="a"*64) == 11
    assert service.create_product(command, username="maria", idempotency_key="k1", operation_fingerprint="a"*64) == 11
    assert database.connection.execute("SELECT COUNT(*) FROM effects").fetchone()[0] == 1
    with pytest.raises(ValueError, match="outro conteúdo"):
        service.create_product(command, username="maria", idempotency_key="k1", operation_fingerprint="b"*64)


def test_falha_reverte_mutacao_e_diario_juntos():
    database = MemoryDatabase(); products = FakeProductBackend(database); products.fail = True
    service = AssistedProductStockService(products, FakeStockBackend(database))
    with pytest.raises(RuntimeError, match="falha"):
        service.create_product(ProductCreateCommand("", "CAFÉ", Decimal("10")), username="maria",
                               idempotency_key="rollback", operation_fingerprint="c"*64)
    assert database.connection.execute("SELECT COUNT(*) FROM effects").fetchone()[0] == 0
    assert database.connection.execute("SELECT COUNT(*) FROM assistant_operation_journal").fetchone()[0] == 0


class Security:
    def __init__(self): self.session = SimpleNamespace(user=SimpleNamespace(username="maria"))
    def is_expired(self): return False
    def require(self, module, action): return (module, action) in {("produtos", "create"), ("produtos", "edit")}
    def touch(self): pass


class Assisted:
    def __init__(self): self.calls=[]
    def create_product(self, command, **kwargs): self.calls.append(("create", command, kwargs)); return 11
    def move_stock(self, operation, command, **kwargs): self.calls.append((operation, command, kwargs)); return {"movement_id": 2}


def test_gateway_exige_confirmacao_reforcada_sessao_real_e_consumo_unico():
    drafts = ProductStockDraftService(DraftProducts())
    draft = drafts.create_stock(operation="STOCK_RECEIVE", product_id=7, value="2", reason="COMPRA")
    assisted = Assisted()
    management = ProductManagementService(DraftProducts(), SimpleNamespace(), Security(), assisted)
    gateway = NabiCodeProductStockAssistantGateway(management)
    broker = DraftConfirmationService()
    actor = AssistantActor("maria", "GERENTE", "sessao")
    challenge = broker.issue(draft, actor=actor)
    authorization = broker.confirm(token=challenge.token, draft=draft, actor=actor)
    assert authorization.capability.name == "REINFORCED_CONFIRMATION"
    assert gateway.execute(draft, authorization) == {"movement_id": 2}
    assert assisted.calls[0][0] == "STOCK_RECEIVE"
    with pytest.raises(PermissionError): gateway.execute(draft, authorization)


def test_gateway_recusa_usuario_diferente_e_operacao_nao_prevista():
    drafts = ProductStockDraftService(DraftProducts())
    draft = drafts.create_stock(operation="STOCK_RECEIVE", product_id=7, value="2", reason="COMPRA")
    broker = DraftConfirmationService(); actor = AssistantActor("joao", "GERENTE", "s")
    challenge = broker.issue(draft, actor=actor)
    authorization = broker.confirm(token=challenge.token, draft=draft, actor=actor)
    gateway = NabiCodeProductStockAssistantGateway(ProductManagementService(DraftProducts(), SimpleNamespace(), Security(), Assisted()))
    with pytest.raises(PermissionError, match="outro usuário"):
        gateway.execute(draft, authorization)
