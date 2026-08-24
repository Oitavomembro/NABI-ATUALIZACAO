from __future__ import annotations

import argparse
import getpass
import os
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from license_issuer.emitter import load_private_key
from services.update_signature import load_public_catalog, sign_update_manifest
from licensing.license_format import canonical_json


def sign_package(
    source: Path, destination: Path, *, private_key: Path, public_catalog: Path,
    key_id: str, password: bytes,
) -> Path:
    signer = load_private_key(private_key, password=password)
    expected = load_public_catalog(public_catalog).get(key_id)
    actual = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    if expected is None or expected != actual:
        raise ValueError("A chave privada não corresponde ao catálogo público selecionado.")
    with zipfile.ZipFile(source, "r") as archive:
        manifest = __import__("json").loads(archive.read("manifest.json").decode("utf-8"))
        entries = {
            name: archive.read(name) for name in archive.namelist()
            if name != "manifest.json"
        }
    signed = sign_update_manifest(manifest, key_id=key_id, signer=signer)
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("manifest.json", canonical_json(signed) + b"\n")
        for name, data in entries.items():
            archive.writestr(name, data)
    with zipfile.ZipFile(temporary, "r") as archive:
        if bad := archive.testzip():
            raise RuntimeError(f"Pacote assinado corrompido: {bad}")
    os.replace(temporary, destination)
    return destination


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assina pacote incremental NabiCode")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--public-catalog", required=True, type=Path)
    parser.add_argument("--key-id", required=True)
    args = parser.parse_args(argv)
    password = getpass.getpass("Senha da chave privada de atualização: ").encode("utf-8")
    print(sign_package(
        args.source, args.destination, private_key=args.private_key,
        public_catalog=args.public_catalog, key_id=args.key_id, password=password,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
