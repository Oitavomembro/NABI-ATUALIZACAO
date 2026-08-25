from __future__ import annotations

import socket
from unittest.mock import Mock, patch

import pytest

from services.fiscal_service import FiscalResponse, FiscalService


ACCESS_KEY = "29260812345678000195550010000000011000000010"
RESERVATION = {
    "id": "HOMOLOGACAO:55:1:1",
    "environment": "HOMOLOGACAO",
    "model": "55",
    "series": 1,
    "number": 1,
    "status": "RESERVADO",
}


class ScriptedGate:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[dict] = []

    def require(self, **kwargs) -> None:
        self.calls.append(dict(kwargs))
        if self.failure is not None:
            raise self.failure


def bare_service(*, gate: ScriptedGate | None, actor="gerente") -> FiscalService:
    service = object.__new__(FiscalService)
    service._readiness_enforced = gate is not None
    service._readiness_gate = gate
    service._authenticated_fiscal_actor = Mock(return_value=actor)
    return service


def configure_authorization_pipeline(
    service: FiscalService, *, success: bool,
) -> tuple[list[str], list[tuple[str, str]]]:
    pipeline: list[str] = []
    confirmations: list[tuple[str, str]] = []
    service.load_config = lambda: {
        "environment": "HOMOLOGACAO", "certificate_path": "FAKE-NOT-OPENED.pfx",
    }
    service._extract_access_key_from_xml = lambda _value: ""
    service.numbering_status = lambda: [dict(RESERVATION)]
    service.sign_xml = lambda *_args, **_kwargs: pipeline.append("sign") or b"SIGNED-FAKE"
    service.validate_official_xml = lambda *_args, **_kwargs: pipeline.append("schema")
    service._authorization_envelope = (
        lambda *_args, **_kwargs: pipeline.append("envelope") or b"ENVELOPE-FAKE"
    )
    service.transmit = lambda **_kwargs: pipeline.append("transmit") or FiscalResponse(
        success, "100" if success else "539",
        "AUTORIZADO SINTETICO" if success else "REJEITADO SINTETICO",
        "PROTOCOLO-SINTETICO" if success else "",
        access_key=ACCESS_KEY, raw_xml="RESPOSTA-SINTETICA-NAO-XML",
    )
    service.store_document = lambda **_kwargs: pipeline.append("store") or {
        "status": "AUTORIZADO" if success else "REJEITADO",
    }
    service.confirm_number = lambda reservation_id, *, access_key: (
        confirmations.append((reservation_id, access_key))
        or {"status": "CONFIRMADO"}
    )
    return pipeline, confirmations


def test_sem_gate_bloqueia_antes_de_identidade_assinatura_transmissao_e_numeracao():
    service = bare_service(gate=None)
    service.sign_xml = Mock(side_effect=AssertionError("assinatura proibida"))
    service.transmit = Mock(side_effect=AssertionError("rede proibida"))
    service.confirm_number = Mock(side_effect=AssertionError("numeração proibida"))

    with pytest.raises(PermissionError, match="portão de prontidão fiscal"):
        service.authorize_document(
            xml=b"DADO-LOCAL", access_key=ACCESS_KEY, password="FAKE",
            reservation_id=RESERVATION["id"],
        )

    service._authenticated_fiscal_actor.assert_not_called()
    service.sign_xml.assert_not_called()
    service.transmit.assert_not_called()
    service.confirm_number.assert_not_called()


def test_gate_recusa_numeracao_pendente_antes_de_config_certificado_ou_rede():
    gate = ScriptedGate(ValueError("numeração fiscal ainda não inicializada"))
    service = bare_service(gate=gate)
    service.load_config = Mock(side_effect=AssertionError("configuração não deve ser lida depois da recusa"))
    service.sign_xml = Mock(side_effect=AssertionError("certificado proibido"))
    service.transmit = Mock(side_effect=AssertionError("rede proibida"))

    with pytest.raises(ValueError, match="numeração fiscal"):
        service.authorize_document(
            xml=b"DADO-LOCAL", access_key=ACCESS_KEY, password="FAKE",
            reservation_id=RESERVATION["id"],
        )

    assert gate.calls == [{
        "operation": "autorizacao", "model": "55", "password": "FAKE",
        "series": 1, "require_catalog": True, "require_numbering": True,
        "check_revocation": True,
    }]
    service.load_config.assert_not_called()
    service.sign_xml.assert_not_called()
    service.transmit.assert_not_called()


def test_gate_aprovado_ainda_exige_reserva_antes_de_assinar_ou_transmitir():
    gate = ScriptedGate()
    service = bare_service(gate=gate)
    pipeline, confirmations = configure_authorization_pipeline(service, success=True)
    service._extract_access_key_from_xml = Mock(
        side_effect=AssertionError("dado fiscal não deve ser lido sem reserva")
    )

    with pytest.raises(ValueError, match="reserva de numeração é obrigatória"):
        service.authorize_document(
            xml=b"DADO-LOCAL", access_key=ACCESS_KEY, password="FAKE",
        )

    assert len(gate.calls) == 1
    service._extract_access_key_from_xml.assert_not_called()
    assert pipeline == []
    assert confirmations == []


@pytest.mark.parametrize("field,value,message", (
    ("status", "CONFIRMADO", "não está reservada"),
    ("environment", "PRODUCAO", "outro ambiente"),
    ("model", "65", "outro modelo"),
    ("series", 2, "não corresponde"),
    ("number", 2, "não corresponde"),
))
def test_reserva_terminal_ou_divergente_bloqueia_antes_de_assinar(
    field, value, message,
):
    gate = ScriptedGate()
    service = bare_service(gate=gate)
    pipeline, confirmations = configure_authorization_pipeline(service, success=True)
    record = dict(RESERVATION)
    record[field] = value
    service.numbering_status = lambda: [record]

    with pytest.raises(ValueError, match=message):
        service.authorize_document(
            xml=b"DADO-LOCAL", access_key=ACCESS_KEY, password="FAKE",
            reservation_id=RESERVATION["id"],
        )

    assert pipeline == []
    assert confirmations == []


@pytest.mark.parametrize("success", (False, True))
def test_resposta_sintetica_so_confirma_numero_quando_autorizada(success):
    gate = ScriptedGate()
    service = bare_service(gate=gate)
    pipeline, confirmations = configure_authorization_pipeline(service, success=success)

    with patch.object(socket, "socket", side_effect=AssertionError("socket proibido")):
        response, record = service.authorize_document(
            xml=b"DADO-LOCAL", access_key=ACCESS_KEY, password="FAKE",
            reservation_id=RESERVATION["id"],
        )

    assert response.success is success
    assert pipeline == ["sign", "schema", "envelope", "transmit", "store"]
    if success:
        assert confirmations == [(RESERVATION["id"], ACCESS_KEY)]
        assert record["numbering"]["status"] == "CONFIRMADO"
    else:
        assert confirmations == []
        assert "numbering" not in record
    assert gate.calls[0]["require_catalog"] is True
    assert gate.calls[0]["require_numbering"] is True
