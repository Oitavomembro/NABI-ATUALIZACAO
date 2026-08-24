from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from administration.purchase_management_service import PurchaseManagementService


def _service(*, allowed=True, expired=False):
    purchase = Mock(); purchase.repository = Mock()
    suppliers = Mock(); security = Mock()
    security.session = SimpleNamespace(user=SimpleNamespace(username="maria"))
    security.is_expired.return_value = expired; security.require.return_value = allowed
    return PurchaseManagementService(purchase, suppliers, security), purchase, suppliers, security


def test_listagem_limita_volume_e_transporta_ids_reais():
    service, purchase, _suppliers, _security = _service()
    purchase.repository.listar_pedidos.return_value = [{
        "id": 7, "status": "ABERTO", "fornecedor_nome": "NABI", "criado_em": "2026",
        "valor_total": "21.50", "quantidade_pendente": "3.0000", "usuario": "maria",
    }]
    result = service.list_orders("todos", limit=999)
    assert result[0].order_id == 7 and str(result[0].total) == "21.50"
    purchase.repository.listar_pedidos.assert_called_once_with(None, limite=200)


def test_criacao_de_pedido_deriva_usuario_da_sessao():
    service, purchase, _suppliers, security = _service(); purchase.criar_pedido.return_value = 9
    assert service.create_order(3, ({"produto_id": 5, "quantidade": "2", "custo_unitario": "10"},)) == 9
    assert purchase.criar_pedido.call_args.kwargs["usuario"] == "maria"
    security.require.assert_called_with("compras", "create")


def test_recebimento_chama_servico_oficial_exatamente_uma_vez_sem_efeitos_paralelos():
    service, purchase, _suppliers, security = _service(); purchase.receber.return_value = "resultado"
    items = ({"pedido_item_id": 11, "quantidade": "2", "custo_unitario": "8"},)
    assert service.receive_order(7, items, document="NF1", create_payable=True, due_date="2026-09-01") == "resultado"
    purchase.receber.assert_called_once()
    call = purchase.receber.call_args
    assert call.args == (7, items)
    assert call.kwargs["usuario"] == "maria" and call.kwargs["gerar_conta_pagar"] is True
    security.require.assert_called_with("compras", "receive")


def test_fornecedor_usa_repositorio_oficial_e_validacao():
    service, _purchase, suppliers, _security = _service(); suppliers.criar.return_value = 12
    assert service.create_supplier("  Fornecedor A  ", legal_name="Empresa A", document="123") == 12
    suppliers.criar.assert_called_once_with("Fornecedor A", razao_social="Empresa A", cnpj="123")
    with pytest.raises(ValueError): service.create_supplier("   ")


@pytest.mark.parametrize("allowed,expired,missing", ((False,False,False),(True,True,False),(True,False,True)))
def test_falha_fechado_antes_de_consultar_ou_mutar(allowed, expired, missing):
    service, purchase, _suppliers, security = _service(allowed=allowed, expired=expired)
    if missing: security.session = None
    with pytest.raises(PermissionError): service.list_orders()
    purchase.repository.listar_pedidos.assert_not_called()
