from __future__ import annotations

import base64
import json
from datetime import date, datetime
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .models import LicenseEdition, LicensePayload


FORMAT_NAME = "NABICODE-LICENSE"
FORMAT_VERSION = 2
_ENVELOPE_FIELDS = {"format", "version", "key_id", "payload", "signature"}
_PAYLOAD_FIELDS = {
    "schema", "license_id", "edition", "customer_name", "machine_fingerprint",
    "issued_at", "valid_until", "grace_days", "features", "revoked",
}


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Campo JSON duplicado: {key}")
        result[key] = value
    return result


def strict_json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON de licença inválido.") from exc


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    text = str(value or "")
    if not text or "=" in text:
        raise ValueError("Base64url não canônico.")
    try:
        decoded = base64.b64decode(
            text + "=" * (-len(text) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, TypeError) as exc:
        raise ValueError("Base64url inválido.") from exc
    if b64url_encode(decoded) != text:
        raise ValueError("Base64url não canônico.")
    return decoded


def payload_mapping(payload: LicensePayload) -> dict:
    return {
        "schema": payload.schema,
        "license_id": payload.license_id,
        "edition": payload.edition.value,
        "customer_name": payload.customer_name,
        "machine_fingerprint": payload.machine_fingerprint,
        "issued_at": payload.issued_at.isoformat().replace("+00:00", "Z"),
        "valid_until": payload.valid_until.isoformat(),
        "grace_days": payload.grace_days,
        "features": list(payload.features),
        "revoked": payload.revoked,
    }


def payload_from_mapping(value: object) -> LicensePayload:
    if not isinstance(value, dict) or set(value) != _PAYLOAD_FIELDS:
        raise ValueError("Campos do payload de licença inválidos.")
    try:
        issued_text = str(value["issued_at"])
        issued = datetime.fromisoformat(issued_text.replace("Z", "+00:00"))
        return LicensePayload(
            schema=value["schema"], license_id=value["license_id"],
            edition=LicenseEdition(str(value["edition"])),
            customer_name=value["customer_name"],
            machine_fingerprint=value["machine_fingerprint"],
            issued_at=issued, valid_until=date.fromisoformat(str(value["valid_until"])),
            grace_days=value["grace_days"], features=tuple(value["features"]),
            revoked=value["revoked"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Payload de licença inválido.") from exc


def verify_envelope(raw: bytes, public_keys: Mapping[str, bytes]) -> LicensePayload:
    envelope = strict_json(raw)
    if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_FIELDS:
        raise ValueError("Envelope de licença inválido.")
    if envelope["format"] != FORMAT_NAME or envelope["version"] != FORMAT_VERSION:
        raise ValueError("Formato de licença incompatível.")
    key_id = str(envelope["key_id"])
    public_bytes = public_keys.get(key_id)
    if public_bytes is None:
        raise ValueError("Chave pública emissora desconhecida.")
    payload_raw = b64url_decode(envelope["payload"])
    payload_value = strict_json(payload_raw)
    if canonical_json(payload_value) != payload_raw:
        raise ValueError("Payload não canônico.")
    signature = b64url_decode(envelope["signature"])
    if len(signature) != 64:
        raise ValueError("Assinatura Ed25519 inválida.")
    try:
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, payload_raw)
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("Assinatura Ed25519 inválida.") from exc
    return payload_from_mapping(payload_value)


def create_envelope(payload: LicensePayload, *, key_id: str, signer) -> bytes:
    payload_raw = canonical_json(payload_mapping(payload))
    signature = signer.sign(payload_raw)
    return canonical_json({
        "format": FORMAT_NAME, "version": FORMAT_VERSION, "key_id": str(key_id),
        "payload": b64url_encode(payload_raw), "signature": b64url_encode(signature),
    }) + b"\n"
