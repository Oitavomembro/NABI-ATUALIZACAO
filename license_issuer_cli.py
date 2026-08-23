"""CLI do emissor. Chave privada e senha nunca pertencem ao runtime."""

from __future__ import annotations

import argparse
import getpass
from datetime import date
from pathlib import Path

from license_issuer.emitter import generate_key_pair, issue_license, load_private_key
from licensing.models import LicenseEdition


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Emissor externo de licenças NabiCode V2")
    subcommands = parser.add_subparsers(dest="command", required=True)
    keygen = subcommands.add_parser("keygen")
    keygen.add_argument("--private", required=True)
    keygen.add_argument("--public-catalog", required=True)
    keygen.add_argument("--key-id", required=True)
    issue = subcommands.add_parser("issue")
    issue.add_argument("--private", required=True)
    issue.add_argument("--key-id", required=True)
    issue.add_argument("--machine-fingerprint", required=True)
    issue.add_argument("--customer", required=True)
    issue.add_argument("--edition", choices=[item.value for item in LicenseEdition], required=True)
    issue.add_argument("--valid-until", required=True)
    issue.add_argument("--feature", action="append", required=True)
    issue.add_argument("--license-id")
    issue.add_argument("--revoked", action="store_true")
    issue.add_argument("--output", required=True)
    options = parser.parse_args(argv)
    password = getpass.getpass("Senha da chave privada: ").encode("utf-8")
    if options.command == "keygen":
        generate_key_pair(
            options.private, options.public_catalog,
            key_id=options.key_id, password=password,
        )
        return 0
    key = load_private_key(options.private, password=password)
    raw = issue_license(
        private_key=key, key_id=options.key_id,
        machine_fingerprint=options.machine_fingerprint,
        customer_name=options.customer, edition=LicenseEdition(options.edition),
        valid_until=date.fromisoformat(options.valid_until),
        features=tuple(options.feature), license_id=options.license_id,
        revoked=options.revoked,
    )
    output = Path(options.output).expanduser().resolve()
    if output.suffix.lower() != ".nabilic":
        raise ValueError("A licença emitida deve usar a extensão .nabilic.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
