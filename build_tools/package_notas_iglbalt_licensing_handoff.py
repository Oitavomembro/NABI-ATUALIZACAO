from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import sys
import tempfile
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from license_issuer.emitter import generate_key_pair
from license_issuer.workflow import IssuanceRequest, review_request, sign_review
from licensing.models import LicenseEdition


OUTPUT = ROOT / "artifacts" / "NotasIglBalt_Licensing_Handoff"
FILES = (
    "docs/INTEGRACAO_LICENCA_NOTAS_IGLBALT.md",
    "docs/LICENCIAMENTO_V2.md",
    "licensing/__init__.py",
    "licensing/gate.py",
    "licensing/license_format.py",
    "licensing/machine.py",
    "licensing/models.py",
    "licensing/service.py",
    "licensing/storage.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build() -> Path:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    (OUTPUT / "sdk").mkdir(parents=True)
    for relative in FILES:
        source = ROOT / relative
        target = OUTPUT / "sdk" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    with tempfile.TemporaryDirectory(prefix="notas-iglbalt-test-key-") as temporary:
        temporary_path = Path(temporary)
        private = temporary_path / "notas-iglbalt-TEST-ONLY-private.pem"
        catalog = OUTPUT / "trusted_public_keys.TEST-ONLY.json"
        password = secrets.token_bytes(32)
        generate_key_pair(
            private, catalog, key_id="notas-iglbalt-test-only-01", password=password,
        )
        request = IssuanceRequest(
            product_id="NOTAS_IGLBALT",
            key_id="notas-iglbalt-test-only-01",
            machine_fingerprint="a" * 64,
            customer_name="EXEMPLO TESTE — NÃO USAR EM PRODUÇÃO",
            edition=LicenseEdition.COMPLETE,
            valid_until=date.today() + timedelta(days=30),
            features=("core",), issued_at=now,
        )
        sign_review(
            review_request(request), private_key_path=private,
            public_catalog_path=catalog, password=password,
            output_path=OUTPUT / "licenca-exemplo.TEST-ONLY.nabilic",
        )

    metadata = {
        "product_id": "NOTAS_IGLBALT",
        "display_name": "Notas IglBalt",
        "expected_product_id": "NOTAS_IGLBALT",
        "sample_machine_fingerprint": "a" * 64,
        "sample_only": True,
        "private_key_included": False,
    }
    (OUTPUT / "CONTRATO.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "LEIA-ME.txt").write_text(
        "PACOTE DE INTEGRAÇÃO — NOTAS IGLBALT\n\n"
        "Este pacote NÃO contém emissor nem chave privada.\n"
        "O catálogo e a licença incluídos são TEST-ONLY, usam fingerprint fictício "
        "e não podem ser enviados em produção.\n\n"
        "No cliente, use LicenseV2Service(expected_product_id='NOTAS_IGLBALT').\n"
        "Antes da distribuição, substitua o catálogo de teste pelo catálogo público "
        "gerado na cerimônia oficial e remova todos os artefatos TEST-ONLY.\n",
        encoding="utf-8",
    )
    candidates = sorted(path for path in OUTPUT.rglob("*") if path.is_file())
    forbidden = [path for path in candidates if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}]
    if forbidden or any(b"PRIVATE KEY" in path.read_bytes() for path in candidates):
        raise RuntimeError("Material privado detectado no pacote de entrega.")
    (OUTPUT / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(OUTPUT).as_posix()}\n" for path in candidates),
        encoding="utf-8",
    )
    archive = OUTPUT.with_suffix(".zip")
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(item for item in OUTPUT.rglob("*") if item.is_file()):
            bundle.write(path, Path(OUTPUT.name) / path.relative_to(OUTPUT))
    return archive


if __name__ == "__main__":
    print(build())
