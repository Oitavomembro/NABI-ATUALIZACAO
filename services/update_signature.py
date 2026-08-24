from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from licensing.license_format import b64url_decode, b64url_encode, canonical_json


def unsigned_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in manifest.items() if key != "signature"}


def sign_update_manifest(manifest: Mapping[str, object], *, key_id: str, signer) -> dict:
    payload = dict(unsigned_manifest(manifest))
    payload["key_id"] = str(key_id).strip()
    if not payload["key_id"]:
        raise ValueError("Identificador da chave de atualização é obrigatório.")
    signature = signer.sign(canonical_json(payload))
    return {**payload, "signature": b64url_encode(signature)}


def load_public_catalog(path: str | Path) -> dict[str, bytes]:
    source = Path(path).expanduser().resolve()
    try:
        document = json.loads(source.read_text(encoding="utf-8-sig"))
        keys = document["keys"]
        if document.get("schema") != 1 or not isinstance(keys, dict):
            raise ValueError
        decoded = {
            str(key_id): base64.b64decode(str(value), validate=True)
            for key_id, value in keys.items()
        }
        if not decoded or any(len(value) != 32 for value in decoded.values()):
            raise ValueError
        return decoded
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Catálogo público de atualização inválido ou ausente.") from exc


def verify_update_manifest(manifest: Mapping[str, object], public_keys: Mapping[str, bytes]) -> None:
    key_id = str(manifest.get("key_id") or "").strip()
    signature_text = str(manifest.get("signature") or "").strip()
    public = public_keys.get(key_id)
    if public is None:
        raise ValueError("Chave pública da atualização é desconhecida.")
    signature = b64url_decode(signature_text)
    if len(signature) != 64:
        raise ValueError("Assinatura da atualização é inválida.")
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, canonical_json(unsigned_manifest(manifest)),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("Assinatura da atualização é inválida.") from exc
