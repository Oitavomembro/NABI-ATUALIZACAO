from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from licensing.license_format import canonical_json, verify_envelope
from licensing.machine import machine_code
from licensing.models import LicenseEdition, LicensePayload

from .emitter import issue_license, load_private_key


_KEY_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,63}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class IssuanceRequest:
    key_id: str
    machine_fingerprint: str
    customer_name: str
    edition: LicenseEdition
    valid_until: date
    features: tuple[str, ...]
    license_id: str | None = None
    revoked: bool = False
    issued_at: datetime | None = None

    def __post_init__(self) -> None:
        key_id = str(self.key_id or "").strip()
        fingerprint = str(self.machine_fingerprint or "").strip().lower()
        customer = str(self.customer_name or "").strip()
        issued = self.issued_at or datetime.now(timezone.utc)
        if not _KEY_ID.fullmatch(key_id):
            raise ValueError("Identificador da chave inválido.")
        if not _HEX_64.fullmatch(fingerprint):
            raise ValueError("Fingerprint da máquina deve possuir 64 caracteres hexadecimais.")
        if not customer:
            raise ValueError("Informe o cliente/titular da licença.")
        if issued.tzinfo is None or issued.utcoffset() is None:
            raise ValueError("Data de emissão deve possuir fuso horário.")
        issued = issued.astimezone(timezone.utc).replace(microsecond=0)
        license_id = str(uuid.UUID(str(self.license_id))) if self.license_id else str(uuid.uuid4())
        # LicensePayload concentra duração AVALIAÇÃO, recursos e tolerância normativa.
        payload = LicensePayload(
            schema=2, license_id=license_id, edition=self.edition,
            customer_name=customer, machine_fingerprint=fingerprint,
            issued_at=issued, valid_until=self.valid_until, grace_days=10,
            features=tuple(self.features), revoked=bool(self.revoked),
        )
        object.__setattr__(self, "key_id", key_id)
        object.__setattr__(self, "machine_fingerprint", fingerprint)
        object.__setattr__(self, "customer_name", payload.customer_name)
        object.__setattr__(self, "license_id", payload.license_id)
        object.__setattr__(self, "issued_at", payload.issued_at)
        object.__setattr__(self, "features", payload.features)

    def review_mapping(self) -> Mapping[str, object]:
        return MappingProxyType({
            "cliente": self.customer_name,
            "edicao": self.edition.value,
            "emissao_utc": self.issued_at.isoformat().replace("+00:00", "Z"),
            "fingerprint": self.machine_fingerprint,
            "codigo_maquina": machine_code(self.machine_fingerprint),
            "validade": self.valid_until.isoformat(),
            "tolerancia_dias": 10,
            "recursos": self.features,
            "license_id": self.license_id,
            "key_id": self.key_id,
            "revogada": self.revoked,
        })


@dataclass(frozen=True, slots=True)
class IssuanceReview:
    request: IssuanceRequest
    digest: str
    summary: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class IssuedArtifact:
    path: Path
    sha256: str
    payload: LicensePayload


def review_request(request: IssuanceRequest) -> IssuanceReview:
    summary = request.review_mapping()
    digest = hashlib.sha256(canonical_json(dict(summary))).hexdigest()
    return IssuanceReview(request, digest, summary)


def parse_machine_request(raw: bytes) -> tuple[str, str]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Solicitação da máquina inválida.") from exc
    if not isinstance(value, dict) or set(value) != {"machine_code", "machine_fingerprint"}:
        raise ValueError("Solicitação da máquina possui campos inválidos.")
    fingerprint = str(value["machine_fingerprint"] or "").strip().lower()
    if not _HEX_64.fullmatch(fingerprint):
        raise ValueError("Fingerprint da solicitação é inválido.")
    expected_code = machine_code(fingerprint)
    if str(value["machine_code"] or "").strip() != expected_code:
        raise ValueError("Código e fingerprint da máquina não correspondem.")
    return fingerprint, expected_code


def load_public_catalog(path: str | os.PathLike[str]) -> dict[str, bytes]:
    try:
        value = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Catálogo de chaves públicas não pôde ser lido.") from exc
    if not isinstance(value, dict) or set(value) != {"schema", "keys"} or value["schema"] != 1:
        raise ValueError("Catálogo de chaves públicas inválido.")
    if not isinstance(value["keys"], dict) or not value["keys"]:
        raise ValueError("Catálogo público não possui chaves.")
    result: dict[str, bytes] = {}
    for key_id, encoded in value["keys"].items():
        if not _KEY_ID.fullmatch(str(key_id)):
            raise ValueError("Identificador inválido no catálogo público.")
        try:
            raw = base64.b64decode(str(encoded), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Chave pública inválida no catálogo.") from exc
        if len(raw) != 32:
            raise ValueError("Chave pública Ed25519 deve possuir 32 bytes.")
        result[str(key_id)] = raw
    return result


def verify_license_file(
    license_path: str | os.PathLike[str], public_catalog_path: str | os.PathLike[str],
) -> LicensePayload:
    catalog = load_public_catalog(public_catalog_path)
    return verify_envelope(Path(license_path).expanduser().resolve().read_bytes(), catalog)


def request_from_existing(
    license_path: str | os.PathLike[str], public_catalog_path: str | os.PathLike[str],
    *, valid_until: date, issued_at: datetime | None = None, revoked: bool = False,
) -> IssuanceRequest:
    previous = verify_license_file(license_path, public_catalog_path)
    issued = (issued_at or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    if issued <= previous.issued_at:
        raise ValueError("A renovação/revogação deve ter emissão posterior à licença anterior.")
    if not revoked and valid_until <= previous.valid_until:
        raise ValueError("A renovação deve ampliar a validade da licença anterior.")
    return IssuanceRequest(
        key_id=_envelope_key_id(Path(license_path).expanduser().resolve().read_bytes()),
        machine_fingerprint=previous.machine_fingerprint,
        customer_name=previous.customer_name,
        edition=previous.edition,
        valid_until=valid_until,
        features=previous.features,
        license_id=previous.license_id,
        revoked=revoked,
        issued_at=issued,
    )


def _envelope_key_id(raw: bytes) -> str:
    try:
        value = json.loads(raw.decode("utf-8"))
        key_id = str(value["key_id"])
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Envelope de licença inválido.") from exc
    if not _KEY_ID.fullmatch(key_id):
        raise ValueError("Identificador da chave emissora inválido.")
    return key_id


def sign_review(
    review: IssuanceReview,
    *,
    private_key_path: str | os.PathLike[str],
    public_catalog_path: str | os.PathLike[str],
    password: bytes,
    output_path: str | os.PathLike[str],
) -> IssuedArtifact:
    if review_request(review.request).digest != review.digest:
        raise ValueError("A revisão mudou; revise novamente antes de assinar.")
    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".nabilic":
        raise ValueError("O arquivo emitido deve usar a extensão .nabilic.")
    if output.exists():
        raise FileExistsError("O arquivo de saída já existe e não será sobrescrito.")
    private_key = load_private_key(private_key_path, password=password)
    request = review.request
    public = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    expected_public = load_public_catalog(public_catalog_path).get(request.key_id)
    if expected_public is None:
        raise ValueError("A chave da revisão não existe no catálogo público.")
    if public != expected_public:
        raise ValueError("A chave privada não corresponde à chave pública selecionada.")
    raw = issue_license(
        private_key=private_key,
        key_id=request.key_id,
        machine_fingerprint=request.machine_fingerprint,
        customer_name=request.customer_name,
        edition=request.edition,
        valid_until=request.valid_until,
        features=request.features,
        issued_at=request.issued_at,
        license_id=request.license_id,
        revoked=request.revoked,
    )
    payload = verify_envelope(raw, {request.key_id: public})
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return IssuedArtifact(output, hashlib.sha256(raw).hexdigest(), payload)
