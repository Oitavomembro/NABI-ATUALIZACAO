from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from license_issuer.emitter import generate_key_pair, load_private_key
from license_issuer.notas_iglbalt_format import (
    NotasIglBaltLicense, sign_license, verify_license,
)
from license_issuer.workflow import load_public_catalog
from services.windows_data_protector import WindowsDataProtector


KEY_ID = "notas-iglbalt-prod-2026-01"
MACHINE_CODE = "NABI2-D415-40A8-E5E2-6FD0"


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def provision(secret_dir: Path, license_dir: Path) -> dict[str, str]:
    secret_dir = secret_dir.expanduser().resolve()
    license_dir = license_dir.expanduser().resolve()
    private_path = secret_dir / f"{KEY_ID}-private.pem"
    password_path = secret_dir / f"{KEY_ID}-password.dpapi"
    catalog_path = secret_dir / f"{KEY_ID}-public-catalog.json"
    public_raw_path = secret_dir / f"{KEY_ID}-public-key.txt"
    license_path = license_dir / "Notas-IglBalt-HOMOLOGACAO-D415-40A8-E5E2-6FD0.nabilic"
    targets = (private_path, password_path, catalog_path, public_raw_path, license_path)
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise FileExistsError("Cerimônia recusada; arquivos já existem: " + ", ".join(existing))

    password = secrets.token_urlsafe(48).encode("ascii")
    protector = WindowsDataProtector(
        description="Notas IglBalt Ed25519 private key password", machine_scope=False,
    )
    try:
        generate_key_pair(
            private_path, catalog_path, key_id=KEY_ID, password=password,
        )
        _exclusive_write(password_path, protector.protect(password))
        public_raw = load_public_catalog(catalog_path)[KEY_ID]
        if len(public_raw) != 32:
            raise RuntimeError("Chave pública Ed25519 deve possuir 32 bytes.")
        public_b64 = base64.b64encode(public_raw)
        _exclusive_write(public_raw_path, public_b64 + b"\n")
        private_key = load_private_key(private_path, password=password)
        issued_at = datetime.now(timezone.utc).replace(microsecond=0)
        raw = sign_license(NotasIglBaltLicense(MACHINE_CODE, issued_at), private_key)
        verify_license(raw, public_raw)
        _exclusive_write(license_path, raw)
        # Verificação independente após releitura do disco.
        verify_license(
            license_path.read_bytes(),
            base64.b64decode(public_raw_path.read_bytes().strip(), validate=True),
        )
        if private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw) != public_raw:
            raise RuntimeError("Chave pública não corresponde à chave privada.")
        return {
            "key_id": KEY_ID,
            "public_key_base64": public_b64.decode("ascii"),
            "public_key_path": str(public_raw_path),
            "public_catalog_path": str(catalog_path),
            "license_path": str(license_path),
            "license_sha256": hashlib.sha256(raw).hexdigest(),
            "private_key_path": str(private_path),
            "password_protection": "DPAPI_CURRENT_USER",
        }
    except Exception:
        for path in targets:
            path.unlink(missing_ok=True)
        raise
    finally:
        password = b""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-dir", required=True, type=Path)
    parser.add_argument("--license-dir", required=True, type=Path)
    options = parser.parse_args(argv)
    result = provision(options.secret_dir, options.license_dir)
    # Não imprime chave privada nem senha.
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
