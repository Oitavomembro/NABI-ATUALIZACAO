from __future__ import annotations

import zipfile

from build_tools.package_notas_iglbalt_licensing_handoff import build


def test_pacote_de_integracao_nao_transporta_segredo():
    archive = build()
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert any(name.endswith("CONTRATO.json") for name in names)
        assert any(name.endswith("licenca-exemplo.TEST-ONLY.nabilic") for name in names)
        assert any(name.endswith("trusted_public_keys.TEST-ONLY.json") for name in names)
        assert any(name.endswith("license_issuer/notas_iglbalt_format.py") for name in names)
        assert not any(name.lower().endswith((".pem", ".key", ".p12", ".pfx")) for name in names)
        assert all(b"PRIVATE KEY" not in bundle.read(name) for name in names)
