from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from license_issuer.notas_iglbalt_format import verify_license


def audit(public_key_path: Path, license_path: Path) -> dict[str, object]:
    public = base64.b64decode(public_key_path.read_bytes().strip(), validate=True)
    if len(public) != 32:
        raise ValueError("Chave pública Ed25519 não possui 32 bytes.")
    raw = license_path.read_bytes()
    payload = verify_license(raw, public)
    altered = json.loads(raw.decode("utf-8"))
    altered["payload"]["machine_code"] = "NABI2-0000-0000-0000-0000"
    tampered = json.dumps(
        altered, ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        verify_license(tampered, public)
    except ValueError:
        tamper_rejected = True
    else:
        tamper_rejected = False
    if not tamper_rejected:
        raise RuntimeError("Adulteração não foi recusada.")
    return {
        "public_bytes": len(public),
        "verified_product": payload["product_id"],
        "verified_machine": payload["machine_code"],
        "not_before": payload["not_before"],
        "expires_at": payload["expires_at"],
        "tamper_rejected": tamper_rejected,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--license", required=True, type=Path)
    options = parser.parse_args(argv)
    print(json.dumps(audit(options.public_key, options.license), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
