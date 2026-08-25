from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from unittest.mock import Mock

from commercial.application.accountant_delivery_dto import AccountantDeliveryStatus
from commercial.application.accountant_delivery_service import AccountantDeliveryApplicationService
from commercial.infrastructure.accountant_delivery_gateway import LocalFolderAccountantDeliveryGateway


class Security:
    def __init__(self):
        self.allowed = True
        self.session = SimpleNamespace(user=SimpleNamespace(username="operador"))

    def require(self, module, action):
        self.last = (module, action)
        return self.allowed


class Gateway:
    def __init__(self): self.calls = []

    def _call(self, operation, plan):
        self.calls.append((operation, plan))
        states = {
            "prepare": "PREPARADO", "enqueue": "ENFILEIRADO",
            "dispatch": "ENVIADO_AO_TRANSPORTE", "check_receipt": "RECEBIDO_CONFIRMADO",
        }
        return AccountantDeliveryStatus(plan.idempotency_key, states[operation], 0)

    def prepare(self, plan): return self._call("prepare", plan)
    def enqueue(self, plan): return self._call("enqueue", plan)
    def dispatch(self, plan): return self._call("dispatch", plan)
    def check_receipt(self, plan): return self._call("check_receipt", plan)


def outcome(tmp_path):
    package = tmp_path / "pacote.zip"
    package.write_bytes(b"pacote imutavel")
    return SimpleNamespace(
        path=str(package), package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
        cnpj="12345678000195", competence="2026-08", profile="ESSENCIAL",
    )


def reviewed(application, tmp_path, **changes):
    destination = tmp_path / "destino"
    destination.mkdir(exist_ok=True)
    data = dict(
        package=outcome(tmp_path), recipient="Contador Responsável",
        destination=str(destination), cnpj_confirmed=True, consent=True,
    )
    data.update(changes)
    return application.review(**data)


def test_revisao_e_pura_e_acoes_humanas_chamam_uma_porta_por_vez(tmp_path):
    gateway = Gateway()
    application = AccountantDeliveryApplicationService(gateway, Security())
    plan = reviewed(application, tmp_path)
    assert gateway.calls == []
    assert application.prepare(plan).status == "PREPARADO"
    assert application.enqueue(plan).status == "ENFILEIRADO"
    assert application.dispatch(plan).status == "ENVIADO_AO_TRANSPORTE"
    assert application.check_receipt(plan).status == "RECEBIDO_CONFIRMADO"
    assert [call[0] for call in gateway.calls] == [
        "prepare", "enqueue", "dispatch", "check_receipt"
    ]


@pytest.mark.parametrize("field,value,message", [
    ("cnpj_confirmed", 1, "CNPJ"),
    ("consent", 1, "consentimento"),
    ("recipient", "\x00contador", "destinatário"),
    ("destination", "inexistente", "pasta"),
])
def test_revisao_recusa_confirmacao_implicita_e_destino_invalido(
    tmp_path, field, value, message
):
    application = AccountantDeliveryApplicationService(Gateway(), Security())
    with pytest.raises(ValueError, match=message):
        reviewed(application, tmp_path, **{field: value})


def test_pacote_adulterado_e_sessao_trocada_falham_antes_da_porta(tmp_path):
    security = Security()
    gateway = Gateway()
    application = AccountantDeliveryApplicationService(gateway, security)
    plan = reviewed(application, tmp_path)
    with open(plan.package_path, "ab") as package:
        package.write(b"adulterado")
    with pytest.raises(ValueError, match="mudou"):
        application.prepare(plan)
    security.session.user.username = "outro"
    with pytest.raises(PermissionError, match="sessão mudou"):
        application.enqueue(plan)
    assert gateway.calls == []


def test_mesmos_dados_retomam_mesma_chave_e_destinatario_ou_pasta_mudam_identidade(tmp_path):
    application = AccountantDeliveryApplicationService(Gateway(), Security())
    first = reviewed(application, tmp_path)
    second = reviewed(application, tmp_path)
    other_recipient = reviewed(application, tmp_path, recipient="Outro Contador")
    other_dir = tmp_path / "outro"
    other_dir.mkdir()
    other_destination = reviewed(application, tmp_path, destination=str(other_dir))
    assert first.idempotency_key == second.idempotency_key
    assert first.idempotency_key != other_recipient.idempotency_key
    assert first.idempotency_key != other_destination.idempotency_key


def test_gateway_consulta_estado_ambiguo_antes_de_qualquer_repeticao(tmp_path):
    gateway = LocalFolderAccountantDeliveryGateway(
        outbox_path=tmp_path / "outbox.sqlite3", spool_dir=tmp_path / "spool"
    )
    service = Mock()
    service.get.return_value = SimpleNamespace(status="DESCONHECIDO")
    service.reconcile_unknown.return_value = SimpleNamespace(
        idempotency_key="acct-12345678", status="FALHA", attempts=1,
        transport_reference="", receipt_sha256="", last_error_code="RECEIPT_NOT_FOUND",
    )
    gateway._service = Mock(return_value=service)
    plan = SimpleNamespace(idempotency_key="acct-12345678")
    status = gateway.check_receipt(plan)
    assert status.status == "FALHA"
    service.reconcile_unknown.assert_called_once_with("acct-12345678")
    service.dispatch.assert_not_called()
    service.enqueue.assert_not_called()
