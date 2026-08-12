from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from helpers.admin_legacy_helpers import migration_phase2_preview_text, migration_phase2_result_text, parse_profile_permissions
from managers.admin_operations_manager import AdminOperationsManager
from unittest import mock
from core.runtime_profile import DatabaseUsageLock


class FakeMaintenance:
    def __init__(self):
        self.calls=[]
    def check(self): self.calls.append('check'); return SimpleNamespace(foreign_key_errors=[])
    def reindex(self): self.calls.append('reindex'); return SimpleNamespace(foreign_key_errors=[])
    def compact(self): self.calls.append('compact'); return SimpleNamespace(foreign_key_errors=[])
    def create_backup(self, **kwargs): self.calls.append(('create',kwargs)); return 'b.db', SimpleNamespace(schema_version=7)
    def restore(self, source): self.calls.append(('restore',source)); return 'safe.db', SimpleNamespace(schema_version=7)


def make_manager(tmp_path):
    config={'licenca_validade':'2026-08-01','licenca_bloqueada':'0'}
    maintenance=FakeMaintenance()
    manager=AdminOperationsManager(
        get_config=config.get, set_config=lambda k,v: config.__setitem__(k,v),
        database_maintenance=maintenance, backup_dir=str(tmp_path), connect=lambda: None,
    )
    return manager, config, maintenance


def test_license_operations_preserve_legacy_policy(tmp_path):
    manager, config, _ = make_manager(tmp_path)
    new_date=manager.renew_license(30, now=datetime(2026,8,7))
    assert new_date == '2026-09-06'
    assert config['licenca_bloqueada']=='0'
    assert manager.toggle_license_block() is True
    assert config['licenca_bloqueada']=='1'
    limit=manager.activate_test_license(now=datetime(2026,8,7,10,0,0))
    assert limit.isoformat(timespec='seconds') == '2026-08-07T10:01:00'


def test_database_actions_and_backup_cleanup(tmp_path):
    manager, _, maintenance = make_manager(tmp_path)
    manager.run_database_action('integridade'); manager.run_database_action('reindex'); manager.run_database_action('vacuum')
    assert maintenance.calls[:3] == ['check','reindex','compact']
    for i in range(12):
        p=Path(tmp_path)/f'{i}.db'; p.write_text('x'); p.touch()
    kept=manager.cleanup_backups(10)
    assert kept == 10
    assert len(list(Path(tmp_path).glob('*.db'))) == 10


def test_admin_helpers_keep_migration_text_and_permissions():
    data={'clientes':[1,2], 'movimentacoes_selecionadas':3, 'saldo_total':12.5, 'clientes_com_credito':1}
    result={'novos':1,'atualizados':1,'movimentacoes':3,'saldo_total':12.5,'backup':'safe.db'}
    assert 'Clientes a importar/atualizar...... 2' in migration_phase2_preview_text(data)
    assert 'Backup de segurança................. safe.db' in migration_phase2_result_text(result)
    assert parse_profile_permissions('vendas:ler,editar\nclientes:ler') == {'vendas':['ler','editar'],'clientes':['ler']}


def test_update_command_carries_original_process_identity(tmp_path):
    manager = AdminOperationsManager(
        get_config=lambda _key: "",
        set_config=lambda _key, _value: None,
        database_maintenance=FakeMaintenance(),
        backup_dir=str(tmp_path),
        connect=lambda: None,
        app_dir=str(tmp_path),
        install_dir=lambda: tmp_path,
        current_version="2.5.1",
    )
    service = mock.Mock()
    service.state_file = tmp_path / "estado.json"
    service.prepare.return_value = {"status": "PREPARADO"}
    with (
        mock.patch.object(manager, "update_service", return_value=service),
        mock.patch.object(DatabaseUsageLock, "_process_started_at", return_value=123.5),
    ):
        _state, command, _cwd = manager.prepare_update(
            "pacote.zip",
            {"version": "2.5.2"},
            "snapshot",
            executable="python.exe",
            source_dir=str(tmp_path),
            frozen=True,
            pid=4321,
        )
    index = command.index("--process-started-at")
    assert command[index + 1] == "123.5"
