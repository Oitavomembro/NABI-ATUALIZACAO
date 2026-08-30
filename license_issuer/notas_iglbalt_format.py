from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)


PRODUCT_ID = "NOTAS_IGLBALT"
EDITION = "COMPLETA"
FEATURES = ("core",)
SCHEMA = 3
_MACHINE_CODE = re.compile(r"^NABI2-[0-9A-F]{4}(?:-[0-9A-F]{4}){3}$")
_PAYLOAD_FIELDS = {
    "schema", "product_id", "edition", "machine_code", "features",
    "issued_at", "not_before", "expires_at",
}
_DOCUMENT_FIELDS = {"payload", "signature"}


def canonical_payload(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(payload), ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class NotasIglBaltLicense:
    machine_code: str
    issued_at: datetime
    not_before: datetime | None = None
    expires_at: datetime | None = None

    def payload(self) -> dict[str, object]:
        machine_code = str(self.machine_code).strip().upper()
        if not _MACHINE_CODE.fullmatch(machine_code):
            raise ValueError("Código da máquina Notas IglBalt inválido.")
        issued_at = _utc(self.issued_at, "issued_at")
        not_before = _optional_utc(self.not_before, "not_before")
        expires_at = _optional_utc(self.expires_at, "expires_at")
        if expires_at is not None and expires_at < (not_before or issued_at):
            raise ValueError("Validade anterior ao início da licença.")
        return {
            "schema": SCHEMA,
            "product_id": PRODUCT_ID,
            "edition": EDITION,
            "machine_code": machine_code,
            "features": list(FEATURES),
            "issued_at": _iso(issued_at),
            "not_before": _iso(not_before) if not_before else None,
            "expires_at": _iso(expires_at) if expires_at else None,
        }


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} deve possuir fuso horário.")
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _optional_utc(value: datetime | None, field: str) -> datetime | None:
    return None if value is None else _utc(value, field)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def sign_license(license_data: NotasIglBaltLicense, private_key: Ed25519PrivateKey) -> bytes:
    payload = license_data.payload()
    signature = private_key.sign(canonical_payload(payload))
    return json.dumps(
        {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")},
        ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8") + b"\n"


def verify_license(raw: bytes, public_key: bytes) -> dict[str, object]:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Licença Notas IglBalt inválida.") from exc
    if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
        raise ValueError("Documento Notas IglBalt possui campos inválidos.")
    payload = document["payload"]
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_FIELDS:
        raise ValueError("Payload Notas IglBalt possui campos inválidos.")
    expected = NotasIglBaltLicense(
        machine_code=str(payload["machine_code"]),
        issued_at=_parse_time(payload["issued_at"], "issued_at"),
        not_before=_parse_optional_time(payload["not_before"], "not_before"),
        expires_at=_parse_optional_time(payload["expires_at"], "expires_at"),
    ).payload()
    if payload != expected:
        raise ValueError("Contrato Notas IglBalt incompatível.")
    try:
        signature = base64.b64decode(str(document["signature"]), validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, canonical_payload(payload),
        )
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise ValueError("Assinatura Notas IglBalt inválida.") from exc
    return payload


def _parse_time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} inválido.")
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")), field)
    except ValueError as exc:
        raise ValueError(f"{field} inválido.") from exc


def _parse_optional_time(value: object, field: str) -> datetime | None:
    return None if value is None else _parse_time(value, field)
