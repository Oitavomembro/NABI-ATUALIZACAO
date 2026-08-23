"""CLI do emissor. Chave privada e senha nunca pertencem ao runtime."""

from __future__ import annotations

import argparse
import getpass
import json
from datetime import date, datetime, timezone

from license_issuer.emitter import generate_key_pair
from license_issuer.workflow import (
    IssuanceRequest, request_from_existing, review_request, sign_review,
    verify_license_file,
)
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
    issue.add_argument("--key-id")
    issue.add_argument("--machine-fingerprint")
    issue.add_argument("--customer")
    issue.add_argument("--edition", choices=[item.value for item in LicenseEdition])
    issue.add_argument("--valid-until", required=True)
    issue.add_argument("--feature", action="append")
    issue.add_argument("--license-id")
    issue.add_argument("--revoked", action="store_true")
    issue.add_argument("--output", required=True)
    issue.add_argument("--renew-from")
    issue.add_argument("--public-catalog", required=True)
    verify = subcommands.add_parser("verify")
    verify.add_argument("--license", required=True)
    verify.add_argument("--public-catalog", required=True)
    options = parser.parse_args(argv)
    if options.command == "keygen":
        password = getpass.getpass("Senha da chave privada: ").encode("utf-8")
        generate_key_pair(
            options.private, options.public_catalog,
            key_id=options.key_id, password=password,
        )
        print("Par de chaves criado. Guarde a chave privada fora do NabiCode e faça duas cópias criptografadas.")
        return 0
    if options.command == "verify":
        payload = verify_license_file(options.license, options.public_catalog)
        print(json.dumps({
            "assinatura": "VALIDA", "cliente": payload.customer_name,
            "edicao": payload.edition.value, "validade": payload.valid_until.isoformat(),
            "license_id": payload.license_id, "revogada": payload.revoked,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if options.renew_from:
        request = request_from_existing(
            options.renew_from, options.public_catalog,
            valid_until=date.fromisoformat(options.valid_until),
            issued_at=now, revoked=options.revoked,
        )
    else:
        missing = [
            name for name, value in (
                ("--key-id", options.key_id),
                ("--machine-fingerprint", options.machine_fingerprint),
                ("--customer", options.customer),
                ("--edition", options.edition),
                ("--feature", options.feature),
            ) if not value
        ]
        if missing:
            parser.error("campos obrigatórios para nova licença: " + ", ".join(missing))
        request = IssuanceRequest(
            key_id=options.key_id, machine_fingerprint=options.machine_fingerprint,
            customer_name=options.customer, edition=LicenseEdition(options.edition),
            valid_until=date.fromisoformat(options.valid_until),
            features=tuple(options.feature), license_id=options.license_id,
            revoked=options.revoked, issued_at=now,
        )
    review = review_request(request)
    print("REVISÃO — NADA FOI ASSINADO")
    print(json.dumps(dict(review.summary), ensure_ascii=False, sort_keys=True, default=list, indent=2))
    print(f"Código da revisão: {review.digest}")
    if input("Digite EMITIR para assinar: ").strip() != "EMITIR":
        print("Emissão cancelada; nenhum arquivo foi criado.")
        return 2
    password = getpass.getpass("Senha da chave privada: ").encode("utf-8")
    artifact = sign_review(
        review, private_key_path=options.private,
        public_catalog_path=options.public_catalog, password=password,
        output_path=options.output,
    )
    print(f"Licença emitida: {artifact.path}")
    print(f"SHA-256: {artifact.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
