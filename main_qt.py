from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from assistant_nabi import (
    AuthenticatedAssistantActivation,
    LLAMA_CPP_B10537_CPU_X64,
    LocalLlamaServer,
    QWEN3_1_7B_Q4_K_M_CANDIDATE,
    UnavailableAssistantService,
    create_read_only_assistant,
)
from commercial.infrastructure.runtime import create_commercial_container
from core.runtime_profile import DatabaseUsageLock, configure_profile_environment
from database import DatabaseManager
from database.schema_initializer import initialize_database
from database.sqlite_connection import backup_database
from services.network_config_service import NetworkConfigService, NetworkPaths
from services.admin_audit_service import AdminAuditService
from services.security_service import SecurityService
from repositories.system_repository import SystemRepository
from ui_qt.app import run

SCHEMA_VERSION = 20


def _create_assistant_activation(database, profile, container):
    """Compõe ativação autenticada; nenhum runtime inicia durante o startup."""

    system = SystemRepository(database.connect)
    security = SecurityService(database.connect)
    security.bootstrap_admin(system.get_config("admin_senha_hash"))
    audit = AdminAuditService(database.connect, logging.getLogger("NabiCode.NabiAudit"))
    ia_root = profile.app_dir / "ia"

    def runtime_factory():
        return LocalLlamaServer(
            runtime_manifest=LLAMA_CPP_B10537_CPU_X64,
            runtime_directory=ia_root / "runtime" / "b10537",
            manifest=QWEN3_1_7B_Q4_K_M_CANDIDATE,
            model_directory=ia_root / "models",
            log_directory=ia_root / "logs",
        )

    def assistant_factory(model, session_id):
        return create_read_only_assistant(
            model=model,
            query_service=container.query,
            security_service=security,
            audit_service=audit,
            session_id=session_id,
        )

    return AuthenticatedAssistantActivation(
        security_service=security,
        runtime_factory=runtime_factory,
        assistant_factory=assistant_factory,
    )


def _network_configuration(profile):
    app_dir = profile.app_dir
    service = NetworkConfigService(
        NetworkPaths(
            app_dir=app_dir,
            config_file=app_dir / "rede_local.json",
            installation_file=app_dir / "instalacao_concluida.json",
            local_db=profile.paths.database,
            server_dir=Path("C:/NabiCode/BancoCompartilhado"),
            server_db=Path("C:/NabiCode/BancoCompartilhado/fichario_moveis_compartilhado.db"),
        )
    )
    return service.load()


def _schema_version(database: DatabaseManager) -> int:
    if not database.database_path.exists():
        return 0
    try:
        row = database.fetch_one(
            "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
        )
        return int(row[0]) if row else 0
    except Exception:
        return 0


def _initialize(database: DatabaseManager, profile, network_mode: bool, network_role: str) -> None:
    last_update = {"executada": False, "de": 0, "para": SCHEMA_VERSION, "backup": ""}

    def backup_before_update(previous: int, target: int) -> str:
        profile.paths.backups.mkdir(parents=True, exist_ok=True)
        destination = profile.paths.backups / (
            f"pre_qt_schema_{previous}_{target}_{datetime.now():%Y%m%d_%H%M%S}.db"
        )
        backup_database(database.database_path, destination, network_mode=network_mode)
        return str(destination)

    initialize_database(
        db_name=str(database.database_path),
        backup_dir=str(profile.paths.backups),
        pdf_dir=str(profile.paths.pdfs),
        schema_version=SCHEMA_VERSION,
        last_database_update=last_update,
        network_mode=network_mode,
        network_role=network_role,
        connect=database.connect,
        read_existing_version=lambda: _schema_version(database),
        backup_before_update=backup_before_update,
    )


def main(argv=None) -> int:
    qt = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    profile = configure_profile_environment("PRODUCAO")
    configuration = _network_configuration(profile)
    database_path = profile.validate_database(
        configuration.get("db_path") or profile.paths.database
    )
    network_mode = configuration.get("modo") == "rede"
    network_role = str(configuration.get("papel") or "local")
    lock = DatabaseUsageLock(database_path, f"{profile.profile}-QT")
    try:
        lock.acquire()
        database = DatabaseManager(database_path, network_mode=network_mode, logger=logging.getLogger("NabiCode.Qt"))
        _initialize(database, profile, network_mode, network_role)
        container = create_commercial_container(database, pdf_dir=profile.paths.pdfs)
        assistant_activation = _create_assistant_activation(database, profile, container)
        qt.aboutToQuit.connect(assistant_activation.stop)
        return run(
            container.application,
            argv,
            cash_label="Caixa ativo",
            profile_label=f"{profile.label} • COMERCIAL / NÃO FISCAL",
            assistant_service=UnavailableAssistantService(
                "Clique em Ativar Nabi e autentique um usuário autorizado. "
                "O modelo local somente será iniciado depois da validação."
            ),
            assistant_activation=assistant_activation,
        )
    except Exception as error:
        QMessageBox.critical(None, "NabiCode", str(error) or "Não foi possível iniciar o PDV Qt.")
        return 1
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
