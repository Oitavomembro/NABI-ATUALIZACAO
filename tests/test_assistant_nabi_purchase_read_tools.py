from decimal import Decimal
from types import SimpleNamespace

from assistant_nabi import AssistantActor, ReadOnlyToolRegistry, ToolRequest
from assistant_nabi.purchase_read_tools import register_purchase_read_tools


class Permissions:
    def __init__(self, allowed=True): self.allowed = allowed
    def allows(self, actor, module, action):
        return self.allowed and module == "compras" and action == "view"


class Audit:
    def record(self, **event): pass


class Purchases:
    def __init__(self): self.calls = []
    def list_suppliers(self):
        self.calls.append(("suppliers",))
        return (SimpleNamespace(supplier_id=2, name="NABI", legal_name="SEGREDO", document="123", active=True),)
    def list_orders(self, status, *, limit):
        self.calls.append(("orders", status, limit))
        return (SimpleNamespace(order_id=7, status="ABERTO", supplier_name="NABI", created_at="2026-08-24", total=Decimal("20.50"), pending_quantity=Decimal("2"), user="interno"),)
    def get_order(self, order_id):
        self.calls.append(("order", order_id))
        return {"id": order_id, "status": "PARCIAL", "fornecedor_nome": "NABI", "fornecedor_cnpj": "oculto", "observacao": "oculta", "itens": ({"id": 11, "produto_id": 5, "codigo": "P5", "nome": "CAFÉ", "quantidade_pedida": Decimal("3"), "quantidade_recebida": Decimal("1"), "quantidade_pendente": Decimal("2"), "custo_unitario": Decimal("8.25"), "observacao": "oculta"},)}


def harness(*, allowed=True, service=None):
    registry = ReadOnlyToolRegistry(permissions=Permissions(allowed), audit=Audit())
    register_purchase_read_tools(registry, service)
    return registry, AssistantActor("maria", "OPERADOR", "sessao")


def test_consultas_expoem_payload_minimo_e_ids_reais():
    service = Purchases(); registry, actor = harness(service=service)
    suppliers = registry.execute(ToolRequest("compras.listar_fornecedores", {}), actor=actor)
    orders = registry.execute(ToolRequest("compras.listar_pedidos", {"status": "TODOS"}), actor=actor)
    detail = registry.execute(ToolRequest("compras.consultar_pedido", {"order_id": 7}), actor=actor)
    assert dict(suppliers.payload["items"][0]) == {
        "supplier_id": 2, "name": "NABI", "active": True,
    }
    assert orders.payload["items"][0]["order_id"] == 7
    assert orders.payload["items"][0]["total"] == "20.50"
    assert "user" not in orders.payload["items"][0]
    assert detail.payload["items"][0]["product_id"] == 5
    assert "fornecedor_cnpj" not in detail.payload and "observacao" not in detail.payload
    assert service.calls == [("suppliers",), ("orders", "TODOS", 50), ("order", 7)]


def test_status_fora_do_schema_e_permissao_negada_nao_consultam():
    service = Purchases(); registry, actor = harness(service=service)
    assert not registry.execute(ToolRequest("compras.listar_pedidos", {"status": "APAGAR"}), actor=actor).success
    denied, actor = harness(allowed=False, service=service)
    assert not denied.execute(ToolRequest("compras.listar_fornecedores", {}), actor=actor).success
    assert service.calls == []


def test_servico_ausente_nao_registra_ferramentas():
    registry, actor = harness(service=None)
    result = registry.execute(ToolRequest("compras.listar_fornecedores", {}), actor=actor)
    assert not result.success and result.message == "Ferramenta não registrada."
