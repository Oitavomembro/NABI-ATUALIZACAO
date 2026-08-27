from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from licensing.license_format import create_envelope
from licensing.models import LicenseEdition, LicensePayload


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _outside_repository(path: str | os.PathLike[str]) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved == REPOSITORY_ROOT or REPOSITORY_ROOT in resolved.parents:
        raise ValueError("A chave privada deve permanecer fora do repositório.")
    return resolved


def generate_key_pair(
    private_path: str | os.PathLike[str], public_catalog_path: str | os.PathLike[str],
    *, key_id: str, password: bytes,
) -> tuple[Path, Path]:
    if not password or len(password) < 12:
        raise ValueError("A senha da chave privada deve possuir ao menos doze caracteres.")
    private_target = _outside_repository(private_path)
    public_target = Path(public_catalog_path).expanduser().resolve()
    if private_target.exists():
        raise FileExistsError("A chave privada já existe; não será sobrescrita.")
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password),
    )
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    private_target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(private_target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(private_raw)
        handle.flush()
        os.fsync(handle.fileno())
    public_target.parent.mkdir(parents=True, exist_ok=True)
    public_target.write_text(json.dumps({
        "schema": 1,
        "keys": {str(key_id): base64.b64encode(public_raw).decode("ascii")},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return private_target, public_target


def load_private_key(path: str | os.PathLike[str], *, password: bytes) -> Ed25519PrivateKey:
    source = _outside_repository(path)
    key = serialization.load_pem_private_key(source.read_bytes(), password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("A chave fornecida não é Ed25519.")
    return key


def issue_license(
    *, private_key: Ed25519PrivateKey, key_id: str, machine_fingerprint: str,
    customer_name: str, edition: LicenseEdition, valid_until: date,
    features: tuple[str, ...], issued_at: datetime | None = None,
    license_id: str | None = None, revoked: bool = False,
    product_id: str = "NABICODE",
) -> bytes:
    payload = LicensePayload(
        schema=2 if product_id == "NABICODE" else 3,
        license_id=license_id or str(uuid.uuid4()), edition=edition,
        customer_name=customer_name, machine_fingerprint=machine_fingerprint,
        issued_at=issued_at or datetime.now(timezone.utc), valid_until=valid_until,
        grace_days=10, features=features, revoked=bool(revoked), product_id=product_id,
    )
    return create_envelope(payload, key_id=key_id, signer=private_key)
