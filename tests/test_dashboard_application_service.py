from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from administration.dashboard_application_service import DashboardApplicationService


def _service(*, allowed=True, expired=False):
    repository = Mock(); repository.indicators.return_value = "indicadores"
    repository.day_history_page.return_value = "historico"
    security = Mock(); security.session = SimpleNamespace(user=SimpleNamespace(username="maria"))
    security.is_expired.return_value = expired; security.require.return_value = allowed
    return DashboardApplicationService(repository, security), repository, security


def test_snapshot_exige_permissao_e_limita_paginacao():
    service, repository, security = _service()
    snapshot = service.load(limit=999, offset=-3)
    assert snapshot.indicators == "indicadores" and snapshot.history == "historico"
    repository.day_history_page.assert_called_once_with(limit=100, offset=0)
    security.require.assert_called_once_with("dashboard", "view")
    security.touch.assert_called_once_with()


def test_resumo_lateral_usa_fachada_autorizada():
    service, repository, security = _service()
    repository.client_summary.return_value = "resumo"
    assert service.load_client_summary() == "resumo"
    repository.client_summary.assert_called_once_with()
    security.require.assert_called_once_with("dashboard", "view")
    security.touch.assert_called_once_with()


@pytest.mark.parametrize("allowed,expired,missing", ((False,False,False),(True,True,False),(True,False,True)))
def test_sessao_invalida_falha_antes_de_consultar(allowed, expired, missing):
    service, repository, security = _service(allowed=allowed, expired=expired)
    if missing: security.session = None
    with pytest.raises(PermissionError): service.load()
    repository.indicators.assert_not_called(); repository.day_history_page.assert_not_called()
