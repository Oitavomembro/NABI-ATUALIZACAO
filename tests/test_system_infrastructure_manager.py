from pathlib import Path
from types import SimpleNamespace

import managers.system_infrastructure_manager as module
from managers.system_infrastructure_manager import SystemInfrastructureManager


def make_manager(tmp_path, **overrides):
    values = dict(
        database_manager=object(),
        db_name=str(tmp_path / "db.sqlite"),
        backup_dir=str(tmp_path / "backup"),
        pdf_dir="pdf_cupons_moveis",
        rollback_dir=str(tmp_path / "rollback"),
        diagnostic_dir=str(tmp_path / "diagnostics"),
        update_state_file=str(tmp_path / "update.json"),
        app_dir=str(tmp_path / "app"),
        source_dir=str(tmp_path / "source"),
        app_version="2.4.88",
        schema_version=7,
        last_database_update="2026-08-07",
        network_mode=False,
        network_role="local",
        connect=lambda: None,
        logger=None,
        get_config=lambda key: None,
        set_config=lambda key, value: None,
        required_diagnostic_tables={"clientes", "movimentacoes", "configuracoes", "categorias_produtos", "produtos"},
    )
    values.update(overrides)
    return SystemInfrastructureManager(**values)


def test_initialize_database_preserves_original_arguments(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(module, "initialize_database", lambda **kwargs: captured.update(kwargs) or "ok")
    manager = make_manager(tmp_path)

    assert manager.initialize_database() == "ok"
    assert captured["db_name"] == manager.db_name
    assert captured["backup_dir"] == manager.backup_dir
    assert captured["pdf_dir"] == "pdf_cupons_moveis"
    assert captured["schema_version"] == 7
    assert captured["read_existing_version"] == manager.read_existing_schema_version
    assert captured["backup_before_update"] == manager.backup_before_update


def test_install_dir_uses_source_dir_when_not_frozen(tmp_path, monkeypatch):
    monkeypatch.delattr(module.sys, "frozen", raising=False)
    manager = make_manager(tmp_path)
    assert manager.install_dir() == Path(manager.source_dir).resolve()


def test_validate_after_restart_wires_services(tmp_path, monkeypatch):
    calls = {}

    class FakeValidation:
        def __init__(self, **kwargs):
            calls.update(kwargs)
        def validate_after_restart(self):
            return {"status": "ok"}

    monkeypatch.setattr(module, "UpdateValidationService", FakeValidation)
    manager = make_manager(tmp_path)
    fake_package = object()
    fake_snapshots = SimpleNamespace(restore=lambda snapshot_id: snapshot_id)
    monkeypatch.setattr(manager, "updates", lambda: fake_package)
    monkeypatch.setattr(manager, "snapshots", lambda: fake_snapshots)

    assert manager.validate_after_restart() == {"status": "ok"}
    assert calls["package_service"] is fake_package
    assert calls["diagnostics_factory"] == manager.diagnostics
    assert calls["app_version"] == "2.4.88"
