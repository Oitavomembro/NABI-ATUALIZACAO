"""Ferramenta restrita de licença; não inicializa banco, Legacy, Qt ou Fiscal."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from core.runtime_profile import configure_profile_environment
from licensing.runtime import build_runtime_license_service
from licensing.machine import machine_code, machine_fingerprint


def _result(decision) -> dict:
    payload = decision.payload
    return {
        "state": decision.state.value,
        "reason": decision.reason,
        "machine_code": decision.machine_code,
        "license_id": payload.license_id if payload else "",
        "edition": payload.edition.value if payload else "",
        "valid_until": payload.valid_until.isoformat() if payload else "",
        "grace_days_remaining": decision.grace_days_remaining,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Administração restrita da licença NabiCode V2")
    parser.add_argument("--profile", choices=("TESTE", "PRODUCAO"), default="PRODUCAO")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--status", action="store_true")
    actions.add_argument("--request", action="store_true")
    actions.add_argument("--activate", metavar="ARQUIVO_NABILIC")
    options = parser.parse_args(argv)
    os.environ["NABICODE_PROFILE"] = options.profile
    profile = configure_profile_environment(options.profile)
    if options.request:
        fingerprint = machine_fingerprint()
        print(json.dumps({
            "machine_code": machine_code(fingerprint),
            "machine_fingerprint": fingerprint,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    service = build_runtime_license_service(profile.app_dir)
    if options.activate:
        decision = service.activate(Path(options.activate).expanduser().resolve())
    else:
        decision = service.evaluate()
    print(json.dumps(_result(decision), ensure_ascii=False, sort_keys=True))
    return 0 if decision.operational else 3


if __name__ == "__main__":
    raise SystemExit(main())
