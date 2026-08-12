from __future__ import annotations

import os
from typing import Any, Callable


class LegacyAuditFacade:
    def __init__(
        self,
        service,
        *,
        event_bus,
        events_enabled: Callable[[], bool],
        database_path: str,
    ) -> None:
        self.service = service
        self.event_bus = event_bus
        self.events_enabled = events_enabled
        self.database_path = database_path

    def record(
        self,
        modulo,
        acao,
        objeto="",
        detalhes="",
        resultado="SUCESSO",
        usuario="Sistema",
    ) -> None:
        self.service.record_event(
            modulo,
            acao,
            object_id=objeto,
            details=detalhes,
            result=resultado,
            user=usuario,
            event_bus=self.event_bus,
            events_enabled=self.events_enabled(),
            database_exists=os.path.exists(self.database_path),
        )


class LegacySystemFacade:
    def __init__(self, repository) -> None:
        self.repository = repository

    def add_client_history(self, cliente_id, evento, detalhes="") -> None:
        if cliente_id:
            self.repository.add_client_history(cliente_id, evento, detalhes)

    def get_config(self, key):
        return self.repository.get_config(key)

    def fiscal_mode_enabled(self) -> bool:
        return (self.get_config("modo_operacao") or "COMERCIAL").strip().upper() == "FISCAL"

    def set_config(self, key, value) -> None:
        self.repository.set_config(key, value)


class LegacyInfrastructureFacade:
    def __init__(self, manager, diagnostics_formatter: Callable[[Any], str]) -> None:
        self.manager = manager
        self.diagnostics_formatter = diagnostics_formatter

    def initialize_database(self):
        return self.manager.initialize_database()

    def snapshot_service(self):
        return self.manager.snapshots()

    def create_snapshot(self, motivo="manual"):
        return self.snapshot_service().create(motivo)

    def list_snapshots(self):
        return self.snapshot_service().list()

    def restore_snapshot(self, snapshot_id):
        return self.snapshot_service().restore(snapshot_id)

    def backup_service(self):
        return self.manager.backups()

    def diagnostics_service(self):
        return self.manager.diagnostics()

    def install_dir(self):
        return self.manager.install_dir()

    def validate_after_restart(self):
        return self.manager.validate_after_restart()

    def execute_diagnostics(self):
        return self.diagnostics_service().run(save_report=True)

    def format_diagnostics(self, result):
        return self.diagnostics_formatter(result)
