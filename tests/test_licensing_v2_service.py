from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from licensing.gate import Capability, LicenseGate
from licensing.license_format import create_envelope
from licensing.models import LicenseEdition, LicensePayload, LicenseState
from licensing.service import LicenseV2Service
from licensing.storage import ProtectedStateStore


class Protector:
    def __init__(self, machine=b"A"):
        self.prefix = b"DPAPI:" + machine + b":"

    def protect(self, data):
        return self.prefix + data

    def unprotect(self, data):
        if not data.startswith(self.prefix):
            raise ValueError("outra máquina")
        return data[len(self.prefix):]


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def setup_service(tmp_path, *, fingerprint="a" * 64, protector=None, now=None):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    clock = Clock(now or datetime(2026, 8, 20, 12, tzinfo=timezone.utc))
    service = LicenseV2Service(
        license_path=tmp_path / "license" / "current.nabilic",
        state_store=ProtectedStateStore(tmp_path / "state" / "license_state_v2.dat", protector or Protector()),
        public_keys={"owner": public}, machine_fingerprint=lambda: fingerprint, now=clock,
    )
    return service, private, clock


def document(private, fingerprint="a" * 64, **changes):
    values = {
        "schema": 2, "license_id": str(uuid.uuid4()),
        "edition": LicenseEdition.COMMERCIAL, "customer_name": "CLIENTE",
        "machine_fingerprint": fingerprint,
        "issued_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "valid_until": date(2026, 8, 31), "grace_days": 10,
        "features": ("commercial", "legacy", "qt"), "revoked": False,
    }
    values.update(changes)
    return create_envelope(LicensePayload(**values), key_id="owner", signer=private)


def activate(service, tmp_path, raw):
    source = tmp_path / "entrada.nabilic"
    source.write_bytes(raw)
    return service.activate(source)


def test_ausente_e_estado_ausente_falham_fechados(tmp_path):
    service, private, _clock = setup_service(tmp_path)
    assert service.evaluate().state is LicenseState.INVALID
    service.license_path.parent.mkdir(parents=True)
    service.license_path.write_bytes(document(private))
    assert service.evaluate().reason == "PROTECTED_STATE_MISSING"


def test_ativa_tolerancia_dez_dias_e_bloqueio_no_decimo_primeiro(tmp_path):
    service, private, clock = setup_service(tmp_path)
    assert activate(service, tmp_path, document(private)).state is LicenseState.ACTIVE
    clock.value = datetime(2026, 9, 1, tzinfo=timezone.utc)
    first = service.evaluate()
    assert (first.state, first.grace_days_remaining) == (LicenseState.GRACE, 10)
    clock.value = datetime(2026, 9, 10, 23, 59, tzinfo=timezone.utc)
    assert service.evaluate().state is LicenseState.GRACE
    clock.value = datetime(2026, 9, 11, tzinfo=timezone.utc)
    assert service.evaluate().state is LicenseState.BLOCKED


def test_retrocesso_relevante_do_relogio_bloqueia(tmp_path):
    service, private, clock = setup_service(tmp_path)
    activate(service, tmp_path, document(private))
    clock.value = datetime(2026, 8, 20, 11, 54, tzinfo=timezone.utc)
    assert service.evaluate().state is LicenseState.CLOCK_SUSPECT


def test_copia_para_segunda_maquina_e_dpapi_diferente_falham(tmp_path):
    service, private, _clock = setup_service(tmp_path)
    activate(service, tmp_path, document(private))
    copied, _other_private, _ = setup_service(
        tmp_path, fingerprint="b" * 64, protector=Protector(b"B")
    )
    assert copied.evaluate().state is LicenseState.INVALID


def test_revogacao_assinada_e_atualizacao_sem_rollback(tmp_path):
    service, private, _clock = setup_service(tmp_path)
    license_id = str(uuid.uuid4())
    activate(service, tmp_path, document(private, license_id=license_id))
    revoked = document(
        private, license_id=license_id, revoked=True,
        issued_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
    )
    assert activate(service, tmp_path, revoked).state is LicenseState.REVOKED
    older = document(
        private, license_id=license_id,
        issued_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert activate(service, tmp_path, older).reason == "LICENSE_ROLLBACK"


def test_estado_adulterado_e_excluido_nao_reabrem_licenca(tmp_path):
    service, private, _clock = setup_service(tmp_path)
    activate(service, tmp_path, document(private))
    service.state_store.path.write_bytes(b"forjado")
    assert service.evaluate().state is LicenseState.INVALID
    service.state_store.path.unlink()
    assert service.evaluate().state is LicenseState.INVALID


def test_portao_restrito_preserva_backup_exportacao_diagnostico_e_ativacao(tmp_path):
    service, _private, _clock = setup_service(tmp_path)
    gate = LicenseGate(service.evaluate())
    for capability in (
        Capability.ACTIVATE, Capability.DIAGNOSTIC, Capability.BACKUP, Capability.EXPORT,
    ):
        assert gate.allows(capability)
    for capability in (
        Capability.LEGACY, Capability.QT, Capability.COMMERCIAL_WRITE,
        Capability.FINANCIAL_WRITE, Capability.ADMIN_WRITE,
        Capability.FISCAL_WORKER, Capability.FISCAL_WRITE,
    ):
        assert not gate.allows(capability)
    assert gate.must_block_workers


def test_senha_local_nao_existe_na_api_de_ativacao(tmp_path):
    service, _private, _clock = setup_service(tmp_path)
    with pytest.raises(TypeError):
        service.activate(tmp_path / "x.nabilic", password="senha-mestre")
