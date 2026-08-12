from pathlib import Path
import sys

from database.schema_initializer import initialize_database
from database.sqlite_connection import backup_database, connection_session
from services import BackupService, SystemDiagnostics, SystemSnapshotService, UpdatePackageService, UpdateValidationService


class SystemInfrastructureManager:
    """Centraliza infraestrutura de banco, snapshots, diagnóstico e atualização."""

    def __init__(
        self,
        *,
        database_manager,
        db_name,
        backup_dir,
        pdf_dir,
        rollback_dir,
        diagnostic_dir,
        update_state_file,
        app_dir,
        source_dir,
        app_version,
        schema_version,
        last_database_update,
        network_mode,
        network_role,
        connect,
        logger,
        get_config,
        set_config,
        required_diagnostic_tables,
    ):
        self.database_manager = database_manager
        self.db_name = db_name
        self.backup_dir = backup_dir
        self.pdf_dir = pdf_dir
        self.rollback_dir = rollback_dir
        self.diagnostic_dir = diagnostic_dir
        self.update_state_file = update_state_file
        self.app_dir = app_dir
        self.source_dir = source_dir
        self.app_version = app_version
        self.schema_version = schema_version
        self.last_database_update = last_database_update
        self.network_mode = network_mode
        self.network_role = network_role
        self.connect = connect
        self.logger = logger
        self.get_config = get_config
        self.set_config = set_config
        self.required_diagnostic_tables = set(required_diagnostic_tables)

    def read_existing_schema_version(self):
        if not Path(self.db_name).exists():
            return 0
        with connection_session(self.db_name, timeout=30, network_mode=self.network_mode) as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'"
            ).fetchone()
            if not exists:
                return 0
            row = conn.execute(
                "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
            ).fetchone()
            return int(row[0]) if row and str(row[0]).isdigit() else 0

    def backup_before_update(self, source_version, target_version):
        from datetime import datetime

        folder = Path(self.backup_dir).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / (
            f"pre_atualizacao_banco_v{source_version}_para_v{target_version}_"
            f"{datetime.now():%Y%m%d_%H%M%S}.db"
        )
        backup_database(
            self.db_name,
            str(destination),
            timeout=60,
            network_mode=self.network_mode,
            logger=self.logger,
        )
        return str(destination)

    def initialize_database(self):
        return initialize_database(
            db_name=self.db_name,
            backup_dir=self.backup_dir,
            pdf_dir=self.pdf_dir,
            schema_version=self.schema_version,
            last_database_update=self.last_database_update,
            network_mode=self.network_mode,
            network_role=self.network_role,
            connect=self.connect,
            read_existing_version=self.read_existing_schema_version,
            backup_before_update=self.backup_before_update,
        )

    def snapshots(self):
        return SystemSnapshotService(
            self.database_manager,
            rollback_dir=self.rollback_dir,
            update_state_file=self.update_state_file,
            app_version=self.app_version,
            schema_version=self.schema_version,
        )

    def backups(self):
        return BackupService(
            database_path=self.db_name,
            default_directory=self.backup_dir,
            get_config=self.get_config,
            set_config=self.set_config,
        )

    def diagnostics(self):
        return SystemDiagnostics(
            self.database_manager,
            app_dir=self.app_dir,
            backup_dir=self.backup_dir,
            rollback_dir=self.rollback_dir,
            diagnostic_dir=self.diagnostic_dir,
            app_version=self.app_version,
            schema_version=self.schema_version,
            required_tables=self.required_diagnostic_tables,
            minimum_free_mb=200,
            max_backup_age_days=7,
        )

    def install_dir(self):
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(self.source_dir).resolve()

    def updates(self):
        return UpdatePackageService(
            app_dir=self.app_dir,
            install_dir=self.install_dir(),
            current_version=self.app_version,
        )

    def validate_after_restart(self):
        return UpdateValidationService(
            package_service=self.updates(),
            diagnostics_factory=self.diagnostics,
            restore_snapshot=self.snapshots().restore,
            app_version=self.app_version,
        ).validate_after_restart()
