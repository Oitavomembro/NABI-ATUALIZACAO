from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from licensing.license_format import create_envelope, verify_envelope
from licensing.models import LicenseEdition, LicensePayload


def payload(**changes):
    values = {
        "schema": 2, "license_id": str(uuid.uuid4()),
        "edition": LicenseEdition.COMMERCIAL, "customer_name": "EMPRESA TESTE",
        "machine_fingerprint": "a" * 64,
        "issued_at": datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
        "valid_until": date(2026, 8, 31), "grace_days": 10,
        "features": ("commercial", "legacy", "qt"), "revoked": False,
    }
    values.update(changes)
    return LicensePayload(**values)


def keys():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, {"owner-2026": public}


def test_envelope_canonico_assinado_e_verificado():
    private, public = keys()
    original = payload()
    raw = create_envelope(original, key_id="owner-2026", signer=private)
    assert raw.endswith(b"\n")
    assert verify_envelope(raw, public) == original


def test_adulteracao_de_payload_assinatura_e_chave_sao_rejeitadas():
    private, public = keys()
    raw = create_envelope(payload(), key_id="owner-2026", signer=private)
    envelope = json.loads(raw)
    envelope["payload"] = envelope["payload"][:-1] + (
        "A" if envelope["payload"][-1] != "A" else "B"
    )
    with pytest.raises(ValueError):
        verify_envelope(json.dumps(envelope).encode(), public)
    with pytest.raises(ValueError, match="desconhecida"):
        verify_envelope(raw, {"outra": next(iter(public.values()))})


def test_campos_extras_duplicados_e_json_nao_canonico_falham_fechados():
    private, public = keys()
    raw = create_envelope(payload(), key_id="owner-2026", signer=private)
    envelope = json.loads(raw)
    envelope["extra"] = True
    with pytest.raises(ValueError, match="Envelope"):
        verify_envelope(json.dumps(envelope).encode(), public)
    duplicate = raw.replace(b'"format":', b'"format":"NABICODE-LICENSE","format":', 1)
    with pytest.raises(ValueError, match="duplicado"):
        verify_envelope(duplicate, public)


def test_tolerancia_e_exatamente_dez_dias_e_avaliacao_maximo_trinta():
    with pytest.raises(ValueError, match="dez dias"):
        payload(grace_days=11)
    with pytest.raises(ValueError, match="trinta dias"):
        payload(
            edition=LicenseEdition.EVALUATION,
            issued_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            valid_until=date(2026, 8, 31),
        )
    evaluation = payload(
        edition=LicenseEdition.EVALUATION,
        issued_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        valid_until=date(2026, 8, 30),
    )
    assert evaluation.edition is LicenseEdition.EVALUATION


def test_fingerprint_bruto_nao_faz_parte_do_documento():
    private, _public = keys()
    raw = create_envelope(payload(), key_id="owner-2026", signer=private)
    assert b"machine-guid" not in raw
    assert b"volume-serial" not in raw


def test_produto_assinado_impede_licenca_cruzada_e_preserva_v2_nabicode():
    private, public = keys()
    legacy = payload()
    legacy_raw = create_envelope(legacy, key_id="owner-2026", signer=private)
    assert verify_envelope(
        legacy_raw, public, expected_product_id="NABICODE"
    ).product_id == "NABICODE"

    notas = LicensePayload(
        schema=3, license_id=legacy.license_id, edition=LicenseEdition.COMPLETE,
        customer_name=legacy.customer_name,
        machine_fingerprint=legacy.machine_fingerprint,
        issued_at=legacy.issued_at, valid_until=legacy.valid_until,
        grace_days=10, features=("core",), product_id="NOTAS_IGLBALT",
    )
    notas_raw = create_envelope(notas, key_id="owner-2026", signer=private)
    assert verify_envelope(
        notas_raw, public, expected_product_id="NOTAS_IGLBALT"
    ).product_id == "NOTAS_IGLBALT"
    with pytest.raises(ValueError, match="outro produto"):
        verify_envelope(notas_raw, public, expected_product_id="NABICODE")
    with pytest.raises(ValueError, match="outro produto"):
        verify_envelope(legacy_raw, public, expected_product_id="NOTAS_IGLBALT")
