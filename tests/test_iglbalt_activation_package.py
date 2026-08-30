from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from datetime import date, datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from license_issuer.iglbalt_activation_package import (
    ActivationHistoryRecord, CapacityRequest, append_history_atomic,
    build_activation_package_bytes, finalize_package_with_history,
    load_capacity_private_key, normalize_administrative_cnpj, normalize_limit,
    sign_capacity, verify_activation_package, verify_capacity,
    write_activation_package_atomic,
)
from license_issuer.notas_iglbalt_format import NotasIglBaltLicense, sign_license


NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
MACHINE = "NABI2-AAAA-BBBB-CCCC-DDDD"


def keys(tmp_path):
    license_private = Ed25519PrivateKey.generate()
    capacity_private = Ed25519PrivateKey.generate()
    license_public = license_private.public_key().public_bytes_raw()
    capacity_public = capacity_private.public_key().public_bytes_raw()
    capacity_path = tmp_path / "capacity-private.key"
    capacity_path.write_text(base64.b64encode(capacity_private.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )).decode("ascii"), encoding="utf-8")
    return license_private, license_public, capacity_private, capacity_public, capacity_path


def documents(tmp_path, *, machine=MACHINE, limit=3):
    license_private, license_public, capacity_private, capacity_public, capacity_path = keys(tmp_path)
    license_raw = sign_license(NotasIglBaltLicense(machine, NOW), license_private)
    capacity_raw = sign_capacity(CapacityRequest(machine, limit, NOW), capacity_private)
    return license_raw, capacity_raw, license_public, capacity_public, capacity_path


def package(tmp_path, **kwargs):
    license_raw, capacity_raw, license_public, capacity_public, _path = documents(tmp_path)
    raw = build_activation_package_bytes(
        license_raw=license_raw, capacity_raw=capacity_raw,
        license_public_key=license_public, capacity_public_key=capacity_public,
        machine_code=MACHINE, package_type="NOVA_INSTALACAO", **kwargs,
    )
    return raw, license_public, capacity_public


def rewrite_member(raw: bytes, member: str, transform) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(raw), "r")
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            content = source.read(name)
            target.writestr(name, transform(content) if name == member else content)
    return output.getvalue()


def test_pacote_completo_preserva_licenca_e_assina_capacidade(tmp_path):
    license_raw, capacity_raw, license_public, capacity_public, capacity_path = documents(tmp_path)
    loaded = load_capacity_private_key(capacity_path)
    assert loaded.public_key().public_bytes_raw() == capacity_public
    raw = build_activation_package_bytes(
        license_raw=license_raw, capacity_raw=capacity_raw,
        license_public_key=license_public, capacity_public_key=capacity_public,
        machine_code=MACHINE, package_type="NOVA_INSTALACAO",
    )
    manifest = verify_activation_package(
        raw, license_public_key=license_public,
        capacity_public_key=capacity_public, machine_code=MACHINE,
    )
    assert manifest["max_registered_cnpjs"] == 3
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        assert bundle.read("license.nabilic") == license_raw
        assert bundle.read("capacity.nabicap") == capacity_raw
        assert not any(name.lower().endswith((".key", ".pem", ".pfx")) for name in bundle.namelist())


def test_aumento_de_plano_nao_reemite_licenca(tmp_path):
    _license, capacity, _license_public, capacity_public, _path = documents(tmp_path, limit=5)
    raw = build_activation_package_bytes(
        license_raw=None, capacity_raw=capacity, license_public_key=None,
        capacity_public_key=capacity_public, machine_code=MACHINE,
        package_type="AUMENTO_PLANO",
    )
    manifest = verify_activation_package(
        raw, license_public_key=None, capacity_public_key=capacity_public,
        machine_code=MACHINE,
    )
    assert set(manifest["documents"]) == {"capacity.nabicap"}


def test_renovacao_sem_nova_licenca_falha_fechada(tmp_path):
    _license, capacity, _license_public, capacity_public, _path = documents(tmp_path)
    with pytest.raises(ValueError, match="renovação exigem"):
        build_activation_package_bytes(
            license_raw=None, capacity_raw=capacity, license_public_key=None,
            capacity_public_key=capacity_public, machine_code=MACHINE,
            package_type="RENOVACAO",
        )


@pytest.mark.parametrize("plan,custom,expected", [
    ("INDIVIDUAL", None, 1), ("DUPLO", None, 2),
    ("EMPRESARIAL", None, 3), ("PERSONALIZADO", 10_000, 10_000),
])
def test_planos_usam_total_de_cnpjs_cadastrados(plan, custom, expected):
    assert normalize_limit(plan, custom)[1] == expected


@pytest.mark.parametrize("value", [0, 10_001, -1, "x"])
def test_limite_personalizado_invalido_falha(value):
    with pytest.raises(ValueError, match="limite"):
        normalize_limit("PERSONALIZADO", value)


def test_capacidade_recusa_adulteracao_maquina_e_assinatura(tmp_path):
    _license, raw, _lp, public, _path = documents(tmp_path)
    payload = verify_capacity(raw, public, machine_code=MACHINE)
    assert "max_registered_cnpjs" in payload
    assert "max_active_cnpjs" not in payload
    with pytest.raises(ValueError, match="máquinas diferentes"):
        verify_capacity(raw, public, machine_code="NABI2-0000-0000-0000-0000")
    document = json.loads(raw)
    document["payload"]["max_registered_cnpjs"] = 9
    tampered = json.dumps(document).encode()
    with pytest.raises(ValueError, match="Assinatura"):
        verify_capacity(tampered, public, machine_code=MACHINE)
    wrong_public = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    with pytest.raises(ValueError, match="Assinatura"):
        verify_capacity(raw, wrong_public, machine_code=MACHINE)


def test_validade_da_capacidade_deve_ser_posterior(tmp_path):
    _license, _capacity, _lp, _cp, path = documents(tmp_path)
    private = load_capacity_private_key(path)
    with pytest.raises(ValueError, match="posterior"):
        sign_capacity(CapacityRequest(MACHINE, 3, NOW, NOW), private)


def test_pacote_recusa_maquina_diferente_incompleto_hash_e_assinatura(tmp_path):
    raw, license_public, capacity_public = package(tmp_path)
    with pytest.raises(ValueError, match="outra máquina"):
        verify_activation_package(
            raw, license_public_key=license_public, capacity_public_key=capacity_public,
            machine_code="NABI2-0000-0000-0000-0000",
        )
    incomplete = rewrite_member(raw, "capacity.nabicap", lambda _raw: b"")
    with pytest.raises(ValueError):
        verify_activation_package(
            incomplete, license_public_key=license_public,
            capacity_public_key=capacity_public, machine_code=MACHINE,
        )
    bad_manifest = rewrite_member(
        raw, "manifest.json",
        lambda data: data.replace(b'"sha256":"', b'"sha256":"BAD'),
    )
    with pytest.raises(ValueError, match="Hash"):
        verify_activation_package(
            bad_manifest, license_public_key=license_public,
            capacity_public_key=capacity_public, machine_code=MACHINE,
        )


def test_gravacao_atomica_nao_sobrescreve_e_remove_parcial(tmp_path, monkeypatch):
    raw, _lp, _cp = package(tmp_path)
    output = tmp_path / "cliente.iglbalt-activation"
    write_activation_package_atomic(raw, output)
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        write_activation_package_atomic(raw, output)
    assert output.read_bytes() == before

    record = ActivationHistoryRecord(
        "CLIENTE", "12345678000195", MACHINE, 3, "2027-08-30",
        NOW.isoformat(), "NOVA_INSTALACAO", "EMPRESARIAL", "", "A", "B", "C",
        str(tmp_path / "falha2.iglbalt-activation"), "OPERADOR",
    )
    # Um histórico corrompido faz rollback do pacote recém-gravado.
    (tmp_path / "historico-invalido.json").write_text("{}", encoding="utf-8")
    failing2 = tmp_path / "falha2.iglbalt-activation"
    with pytest.raises(ValueError, match="Histórico"):
        finalize_package_with_history(
            package_raw=raw, output_path=failing2,
            history_path=tmp_path / "historico-invalido.json", record=record,
        )
    assert not failing2.exists()


def test_historico_administrativo_nao_registra_segredos(tmp_path):
    path = tmp_path / "history.json"
    record = ActivationHistoryRecord(
        "CLIENTE", normalize_administrative_cnpj("12.345.678/0001-95"), MACHINE,
        3, "2027-08-30", NOW.isoformat(), "NOVA_INSTALACAO", "EMPRESARIAL",
        "Observação", "A" * 64, "B" * 64, "C" * 64,
        "C:/Licencas/cliente.iglbalt-activation", "ADMIN",
    )
    append_history_atomic(path, record)
    text = path.read_text(encoding="utf-8")
    assert "PRIVATE KEY" not in text
    assert "capacity-private.key" not in text
    assert json.loads(text)[0]["max_registered_cnpjs"] == 3
