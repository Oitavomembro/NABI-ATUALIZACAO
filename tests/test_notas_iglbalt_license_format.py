from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from license_issuer.notas_iglbalt_format import (
    NotasIglBaltLicense, canonical_payload, sign_license, verify_license,
)
from license_issuer.emitter import generate_key_pair
from license_issuer.workflow import IssuanceRequest, review_request, sign_review
from licensing.models import LicenseEdition


NOW = datetime(2026, 8, 27, 12, 34, 56, tzinfo=timezone.utc)
CODE = "NABI2-D415-40A8-E5E2-6FD0"


def keys():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, public


def test_contrato_exato_e_assinatura_independente():
    private, public = keys()
    raw = sign_license(NotasIglBaltLicense(CODE, NOW), private)
    document = json.loads(raw)
    assert set(document) == {"payload", "signature"}
    assert document["payload"] == {
        "schema": 3, "product_id": "NOTAS_IGLBALT", "edition": "COMPLETA",
        "machine_code": CODE, "features": ["core"],
        "issued_at": "2026-08-27T12:34:56Z", "not_before": None,
        "expires_at": None,
    }
    assert canonical_payload(document["payload"]) == json.dumps(
        document["payload"], ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert verify_license(raw, public) == document["payload"]


def test_adulteracao_produto_feature_maquina_e_assinatura_falham():
    private, public = keys()
    raw = sign_license(NotasIglBaltLicense(CODE, NOW), private)
    for field, value in (
        ("product_id", "NABICODE"), ("features", ["core", "fiscal"]),
        ("machine_code", "NABI2-0000-0000-0000-0000"),
    ):
        document = json.loads(raw)
        document["payload"][field] = value
        with pytest.raises(ValueError):
            verify_license(json.dumps(document).encode(), public)
    with pytest.raises(ValueError, match="Assinatura"):
        verify_license(raw, keys()[1])


def test_nao_aceita_campos_extras_ou_formato_nabicode():
    private, public = keys()
    document = json.loads(sign_license(NotasIglBaltLicense(CODE, NOW), private))
    document["payload"]["license_id"] = "não permitido"
    with pytest.raises(ValueError, match="campos"):
        verify_license(json.dumps(document).encode(), public)
    with pytest.raises(ValueError, match="campos"):
        verify_license(b'{"format":"NABICODE-LICENSE"}', public)


def test_workflow_do_emissor_gera_exatamente_o_formato_do_cliente(tmp_path):
    private_path = tmp_path / "fora" / "notas-iglbalt-private.pem"
    catalog_path = tmp_path / "public.json"
    password = b"senha-forte-teste"
    generate_key_pair(
        private_path, catalog_path, key_id="notas-iglbalt-prod-2026-01",
        password=password,
    )
    request = IssuanceRequest(
        product_id="NOTAS_IGLBALT", key_id="notas-iglbalt-prod-2026-01",
        machine_fingerprint=CODE, customer_name="HOMOLOGAÇÃO",
        edition=LicenseEdition.COMPLETE, valid_until=NOW.date(), features=("core",),
        issued_at=NOW,
    )
    artifact = sign_review(
        review_request(request), private_key_path=private_path,
        public_catalog_path=catalog_path, password=password,
        output_path=tmp_path / "homologacao.nabilic",
    )
    document = json.loads(artifact.path.read_bytes())
    assert set(document) == {"payload", "signature"}
    assert document["payload"]["not_before"] is None
    assert document["payload"]["expires_at"] is None
