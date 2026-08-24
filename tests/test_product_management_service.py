from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from administration.product_management_service import ProductManagementService
from commercial.application.action_dto import ActionOrigin


def _service(*, allowed=True, expired=False):
    products = Mock()
    products.search_products.return_value = ("produto",)
    products.product_movements.return_value = ("movimento",)
    products.low_stock_products.return_value = ("baixo",)
    stock = Mock()
    security = Mock()
    security.session = SimpleNamespace(user=SimpleNamespace(username="maria"))
    security.is_expired.return_value = expired
    security.require.return_value = allowed
    return ProductManagementService(products, stock, security), products, stock, security


def test_consultas_exigem_view_e_preservam_ids_reais():
    service, products, _stock, security = _service()
    assert service.search("mesa", limit=25) == ("produto",)
    service.get(17); service.stock(17)
    assert service.movements(17, limit=9) == ("movimento",)
    assert service.low_stock() == ("baixo",)
    products.get_product.assert_called_once_with(17)
    products.product_stock.assert_called_once_with(17)
    products.product_movements.assert_called_once_with(17, limit=9)
    assert security.require.call_count == 5


def test_criar_e_editar_usam_permissoes_distintas():
    service, products, _stock, security = _service()
    service.create("novo"); service.update("edicao")
    assert security.require.call_args_list[0].args == ("produtos", "create")
    assert security.require.call_args_list[1].args == ("produtos", "edit")
    products.create_product.assert_called_once_with("novo")
    products.update_product.assert_called_once_with("edicao")


@pytest.mark.parametrize("method", ("receive", "remove", "adjust"))
def test_movimentacao_deriva_ator_da_sessao_e_exige_confirmacao(method):
    service, _products, stock, _security = _service()
    result = getattr(service, method)("comando", confirmed=True)
    operation = getattr(stock, {"receive":"receive_stock", "remove":"remove_stock", "adjust":"adjust_stock"}[method])
    assert result is operation.return_value
    kwargs = operation.call_args.kwargs
    assert kwargs["confirmed"] is True
    assert kwargs["context"].requested_by == "maria"
    assert kwargs["context"].origin is ActionOrigin.UI


def test_sessao_ausente_expirada_ou_sem_permissao_falha_fechado():
    for service, products, _stock, security in (
        _service(expired=True), _service(allowed=False), _service(),
    ):
        if not security.is_expired.return_value and security.require.return_value:
            security.session = None
        with pytest.raises(PermissionError):
            service.search("")
        products.search_products.assert_not_called()
