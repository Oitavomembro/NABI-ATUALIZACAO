from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

from .notas_iglbalt_format import verify_license as verify_notas_license


PACKAGE_SCHEMA = 1
CAPACITY_SCHEMA = 1
CAPACITY_PRODUCT_ID = "NOTAS_IGLBALT_CAPACITY"
PACKAGE_SUFFIX = ".iglbalt-activation"
MACHINE_CODE = re.compile(r"^NABI2-[0-9A-F]{4}(?:-[0-9A-F]{4}){3}$")
PLANS = {"INDIVIDUAL": 1, "DUPLO": 2, "EMPRESARIAL": 3}
PACKAGE_MEMBERS = {"license.nabilic", "capacity.nabicap", "manifest.json"}


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} deve possuir fuso horário.")
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return _utc(value, "data").isoformat().replace("+00:00", "Z")


def normalize_machine(value: object) -> str:
    machine = str(value or "").strip().upper()
    if not MACHINE_CODE.fullmatch(machine):
        raise ValueError("Código da máquina Notas IglBalt inválido.")
    return machine


def normalize_administrative_cnpj(value: object) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    if len(digits) != 14 or len(set(digits)) == 1:
        raise ValueError("CNPJ principal administrativo inválido.")
    numbers = [int(character) for character in digits]
    for length, weights in (
        (12, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
        (13, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
    ):
        remainder = sum(numbers[index] * weights[index] for index in range(length)) % 11
        expected = 0 if remainder < 2 else 11 - remainder
        if numbers[length] != expected:
            raise ValueError("CNPJ principal administrativo inválido.")
    return digits


def normalize_limit(plan: object, custom_limit: object | None = None) -> tuple[str, int]:
    normalized_plan = str(plan or "").strip().upper()
    if normalized_plan == "PERSONALIZADO":
        try:
            limit = int(custom_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("Informe o limite personalizado de CNPJs.") from exc
    elif normalized_plan in PLANS:
        limit = PLANS[normalized_plan]
    else:
        raise ValueError("Plano comercial inválido.")
    if not 1 <= limit <= 10_000:
        raise ValueError("O limite deve ficar entre 1 e 10.000 CNPJs cadastrados.")
    return normalized_plan, limit


def load_capacity_private_key(path: str | os.PathLike[str]) -> Ed25519PrivateKey:
    source = Path(path).expanduser().resolve()
    try:
        encoded = source.read_text(encoding="utf-8").strip()
        raw = base64.b64decode(encoded, validate=True)
        key = serialization.load_der_private_key(raw, password=None)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError("Chave privada de capacidade inválida ou indisponível.") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("A chave de capacidade deve ser Ed25519 PKCS#8.")
    return key


def load_capacity_public_key(path: str | os.PathLike[str]) -> bytes:
    try:
        raw = base64.b64decode(
            Path(path).expanduser().resolve().read_text(encoding="utf-8").strip(),
            validate=True,
        )
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError("Chave pública de capacidade inválida ou indisponível.") from exc
    if len(raw) != 32:
        raise ValueError("Chave pública de capacidade deve possuir 32 bytes.")
    return raw


@dataclass(frozen=True, slots=True)
class CapacityRequest:
    machine_code: str
    max_registered_cnpjs: int
    issued_at: datetime
    expires_at: datetime | None = None

    def payload(self) -> dict[str, object]:
        issued = _utc(self.issued_at, "issued_at")
        expires = None if self.expires_at is None else _utc(self.expires_at, "expires_at")
        if expires is not None and expires <= issued:
            raise ValueError("Validade da capacidade deve ser posterior à emissão.")
        if not 1 <= int(self.max_registered_cnpjs) <= 10_000:
            raise ValueError("O limite deve ficar entre 1 e 10.000 CNPJs cadastrados.")
        return {
            "expires_at": _iso(expires) if expires else None,
            "issued_at": _iso(issued),
            "machine_code": normalize_machine(self.machine_code),
            "max_registered_cnpjs": int(self.max_registered_cnpjs),
            "product_id": CAPACITY_PRODUCT_ID,
            "schema": CAPACITY_SCHEMA,
        }


def sign_capacity(request: CapacityRequest, private_key: Ed25519PrivateKey) -> bytes:
    payload = request.payload()
    signature = private_key.sign(canonical_json(payload))
    return canonical_json({
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
    }) + b"\n"


def verify_capacity(raw: bytes, public_key: bytes, *, machine_code: str) -> dict[str, object]:
    if not raw or len(raw) > 64 * 1024:
        raise ValueError("Autorização de capacidade vazia ou muito grande.")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Autorização de capacidade não é um JSON válido.") from exc
    if not isinstance(document, dict) or set(document) != {"payload", "signature"}:
        raise ValueError("Envelope de capacidade incompatível.")
    payload = document["payload"]
    fields = {
        "schema", "product_id", "machine_code", "max_registered_cnpjs",
        "issued_at", "expires_at",
    }
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError("Payload de capacidade incompatível.")
    expected = CapacityRequest(
        machine_code=str(payload["machine_code"]),
        max_registered_cnpjs=int(payload["max_registered_cnpjs"]),
        issued_at=_parse_time(payload["issued_at"], "issued_at"),
        expires_at=_parse_optional_time(payload["expires_at"], "expires_at"),
    ).payload()
    if payload != expected:
        raise ValueError("Contrato da capacidade incompatível.")
    try:
        signature = base64.b64decode(str(document["signature"]), validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, canonical_json(payload)
        )
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise ValueError("Assinatura da capacidade inválida.") from exc
    if payload["product_id"] != CAPACITY_PRODUCT_ID or payload["schema"] != CAPACITY_SCHEMA:
        raise ValueError("Capacidade pertence a outro produto ou schema.")
    if payload["machine_code"] != normalize_machine(machine_code):
        raise ValueError("Licença e capacidade pertencem a máquinas diferentes.")
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


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def build_activation_package_bytes(
    *, license_raw: bytes | None, capacity_raw: bytes,
    license_public_key: bytes | None, capacity_public_key: bytes,
    machine_code: str, package_type: str,
) -> bytes:
    machine = normalize_machine(machine_code)
    operation = str(package_type or "").strip().upper()
    if operation not in {"NOVA_INSTALACAO", "AUMENTO_PLANO", "RENOVACAO"}:
        raise ValueError("Tipo de operação do pacote inválido.")
    if operation in {"NOVA_INSTALACAO", "RENOVACAO"} and not license_raw:
        raise ValueError("Nova instalação e renovação exigem a licença V2 original.")
    if license_raw is not None:
        if license_public_key is None:
            raise ValueError("Chave pública da licença V2 é obrigatória.")
        license_payload = verify_notas_license(license_raw, license_public_key)
        if license_payload["machine_code"] != machine:
            raise ValueError("Licença e capacidade pertencem a máquinas diferentes.")
    capacity_payload = verify_capacity(capacity_raw, capacity_public_key, machine_code=machine)
    documents: dict[str, dict[str, object]] = {
        "capacity.nabicap": {
            "sha256": _sha256(capacity_raw), "size": len(capacity_raw),
        }
    }
    if license_raw is not None:
        documents["license.nabilic"] = {
            "sha256": _sha256(license_raw), "size": len(license_raw),
        }
    manifest = {
        "documents": documents,
        "machine_code": machine,
        "max_registered_cnpjs": capacity_payload["max_registered_cnpjs"],
        "package_type": operation,
        "product_id": "NOTAS_IGLBALT",
        "schema": PACKAGE_SCHEMA,
    }
    with tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024) as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            if license_raw is not None:
                bundle.writestr("license.nabilic", license_raw)
            bundle.writestr("capacity.nabicap", capacity_raw)
            bundle.writestr("manifest.json", canonical_json(manifest) + b"\n")
        stream.seek(0)
        return stream.read()


def verify_activation_package(
    raw: bytes, *, license_public_key: bytes | None,
    capacity_public_key: bytes, machine_code: str,
) -> dict[str, object]:
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(raw), "r") as bundle:
            names = set(bundle.namelist())
            if "manifest.json" not in names or "capacity.nabicap" not in names:
                raise ValueError("Pacote de ativação incompleto.")
            if names - PACKAGE_MEMBERS or len(names) != len(bundle.namelist()):
                raise ValueError("Pacote de ativação contém arquivos inesperados ou duplicados.")
            manifest_raw = bundle.read("manifest.json")
            manifest = json.loads(manifest_raw.decode("utf-8"))
            expected_fields = {
                "schema", "product_id", "package_type", "machine_code",
                "max_registered_cnpjs", "documents",
            }
            if not isinstance(manifest, dict) or set(manifest) != expected_fields:
                raise ValueError("Manifesto do pacote é incompatível.")
            if manifest["schema"] != PACKAGE_SCHEMA or manifest["product_id"] != "NOTAS_IGLBALT":
                raise ValueError("Pacote pertence a outro produto ou schema.")
            machine = normalize_machine(machine_code)
            if manifest["machine_code"] != machine:
                raise ValueError("Pacote pertence a outra máquina.")
            documents = manifest["documents"]
            expected_names = names - {"manifest.json"}
            if not isinstance(documents, dict) or set(documents) != expected_names:
                raise ValueError("Manifesto não corresponde ao conteúdo do pacote.")
            payloads: dict[str, bytes] = {}
            for name in expected_names:
                content = bundle.read(name)
                payloads[name] = content
                descriptor = documents[name]
                if not isinstance(descriptor, dict) or set(descriptor) != {"sha256", "size"}:
                    raise ValueError("Descritor de documento inválido no manifesto.")
                if descriptor["sha256"] != _sha256(content) or descriptor["size"] != len(content):
                    raise ValueError("Hash ou tamanho do documento diverge do manifesto.")
    except (zipfile.BadZipFile, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Pacote de ativação inválido.") from exc
    capacity = verify_capacity(
        payloads["capacity.nabicap"], capacity_public_key, machine_code=machine
    )
    if int(manifest["max_registered_cnpjs"]) != int(capacity["max_registered_cnpjs"]):
        raise ValueError("Limite do manifesto diverge da autorização assinada.")
    if "license.nabilic" in payloads:
        if license_public_key is None:
            raise ValueError("Chave pública da licença V2 é obrigatória.")
        license_payload = verify_notas_license(payloads["license.nabilic"], license_public_key)
        if license_payload["machine_code"] != machine:
            raise ValueError("Licença e capacidade pertencem a máquinas diferentes.")
    elif manifest["package_type"] in {"NOVA_INSTALACAO", "RENOVACAO"}:
        raise ValueError("Nova instalação e renovação exigem licença V2 no pacote.")
    return manifest


def write_activation_package_atomic(raw: bytes, output_path: str | os.PathLike[str]) -> Path:
    output = Path(output_path).expanduser().resolve()
    if not str(output).lower().endswith(PACKAGE_SUFFIX):
        raise ValueError(f"O pacote deve usar a extensão {PACKAGE_SUFFIX}.")
    if output.exists():
        raise FileExistsError("O pacote já existe e não será sobrescrito.")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        raise
    return output


@dataclass(frozen=True, slots=True)
class ActivationHistoryRecord:
    customer: str
    administrative_cnpj: str
    machine_code: str
    max_registered_cnpjs: int
    valid_until: str
    issued_at: str
    operation: str
    plan: str
    note: str
    package_sha256: str
    license_sha256: str
    capacity_sha256: str
    package_path: str
    operator: str


def append_history_atomic(
    history_path: str | os.PathLike[str], record: ActivationHistoryRecord,
) -> None:
    if not str(record.customer).strip() or not str(record.operator).strip():
        raise ValueError("Cliente e operador responsável são obrigatórios no histórico.")
    path = Path(history_path).expanduser().resolve()
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Histórico administrativo local está inválido.") from exc
    if not isinstance(current, list):
        raise ValueError("Histórico administrativo local está inválido.")
    current.append(asdict(record))
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(current, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def finalize_package_with_history(
    *, package_raw: bytes, output_path: str | os.PathLike[str],
    history_path: str | os.PathLike[str], record: ActivationHistoryRecord,
) -> Path:
    output = write_activation_package_atomic(package_raw, output_path)
    try:
        append_history_atomic(history_path, record)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output
