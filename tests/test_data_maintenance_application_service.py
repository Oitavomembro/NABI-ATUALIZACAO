from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from administration.data_maintenance_application_service import DataMaintenanceApplicationService


class Security:
    def __init__(self, allowed=True): self.allowed = allowed
    def current_session(self):
        return SimpleNamespace(user=SimpleNamespace(username="admin")) if self.allowed else None
    def require(self, module, action): return self.allowed


class Audit:
    def __init__(self): self.events = []
    def record_event_strict(self, module, action, **kwargs): self.events.append((module, action, kwargs))


class Migration:
    def __init__(self): self.executions = 0
    def preview(self, package):
        return SimpleNamespace(package_sha256="a" * 64, ready=True)
    def execute(self, *args, **kwargs):
        self.executions += 1
        return SimpleNamespace(backup="before.db", inserted={"customers": 1}, updated={})


class Backup:
    def __init__(self, active, tmp_path): self.active, self.tmp_path = active, tmp_path
    def verify_restore_in_temporary(self, source, password=None):
        path = Path(source)
        assert path.resolve() != self.active.resolve()
        return SimpleNamespace(
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            backup_format="SQLITE_LEGACY_UNENCRYPTED", schema_version=32,
        )
    def create(self, directory, prefix):
        target = Path(directory) / f"{prefix}.db"; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.active, target); return str(target)


def make_service(tmp_path, allowed=True):
    active = tmp_path / "active.db"; active.write_bytes(b"sqlite-active")
    audit, migration = Audit(), Migration()
    service = DataMaintenanceApplicationService(
        security=Security(allowed), audit=audit, migration=migration,
        backup=Backup(active, tmp_path), database_path=active,
        backup_directory=tmp_path / "backups", staging_directory=tmp_path / "staging",
        connect=lambda: None, backup_database=lambda source, target: shutil.copy2(source, target),
    )
    return service, audit, migration, active


def test_sem_sessao_nao_previsualiza_nem_verifica(tmp_path):
    service, *_ = make_service(tmp_path, allowed=False)
    with pytest.raises(PermissionError): service.preview_migration("x.nabimig")
    with pytest.raises(PermissionError): service.verify_backup(tmp_path / "x.db")


def test_migracao_exige_hash_digitado_e_audita(tmp_path):
    service, audit, migration, _active = make_service(tmp_path)
    preview = service.preview_migration("x.nabimig")
    with pytest.raises(ValueError):
        service.execute_migration("x.nabimig", categories=("customers",), confirmation="sim")
    assert migration.executions == 0
    result = service.execute_migration(
        "x.nabimig", categories=("customers",),
        confirmation=service.migration_confirmation(preview),
    )
    assert result.inserted == {"customers": 1}
    assert [item[1] for item in audit.events] == ["MIGRACAO_INICIADA", "MIGRACAO_CONCLUIDA"]


def test_preparacao_cria_prebackup_e_nao_altera_banco_ativo(tmp_path):
    service, audit, _migration, active = make_service(tmp_path)
    source = tmp_path / "source.db"; source.write_bytes(b"sqlite-restored")
    before = active.read_bytes()
    verification = service.verify_backup(source)
    prepared = service.prepare_restore(
        source, confirmation=service.restore_confirmation(verification.sha256)
    )
    assert active.read_bytes() == before
    assert Path(prepared.safety_backup).read_bytes() == before
    request = json.loads(Path(prepared.request_file).read_text(encoding="utf-8"))
    assert request["status"] == "AGUARDANDO_HELPER_OFICIAL"
    assert "target_database" not in request
    assert request["profile_database_name"] == active.name
    assert audit.events[-1][1] == "RESTAURACAO_PREPARADA"


def test_confirmacao_errada_nao_cria_staging_ou_prebackup(tmp_path):
    service, *_ = make_service(tmp_path)
    source = tmp_path / "source.db"; source.write_bytes(b"sqlite-restored")
    with pytest.raises(ValueError): service.prepare_restore(source, confirmation="RESTAURAR")
    assert not (tmp_path / "staging").exists()
    assert not (tmp_path / "backups").exists()

