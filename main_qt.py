from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

from assistant_nabi import (
    AuthenticatedAssistantActivation,
    LLAMA_CPP_B10537_CPU_X64,
    LocalLlamaServer,
    QWEN3_1_7B_Q4_K_M_CANDIDATE,
    UnavailableAssistantService,
    NFeEntryDraftService,
    NabiCodeNFeEntryAssistantGateway,
    create_purchase_assistant_components,
    create_draft_assistant,
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
from repositories import NFeImportRepository
from services import NFeImportService
from ui_qt.app import run
from licensing.gate import Capability
from licensing.runtime import evaluate_runtime_gate, startup_block_message

SCHEMA_VERSION = 20


def _create_assistant_activation(
    database, profile, container, nfe_entry_service=None, nfe_import_service=None
):
    """Compõe ativação autenticada; nenhum runtime inicia durante o startup."""

    system = SystemRepository(database.connect)
    security = SecurityService(database.connect)
    security.bootstrap_admin(system.get_config("admin_senha_hash"))
    audit = AdminAuditService(database.connect, logging.getLogger("NabiCode.NabiAudit"))
    ia_root = profile.app_dir / "ia"
    purchase_drafts = purchase_executor = None
    if getattr(container, "purchase_service", None) is not None:
        purchase_drafts, purchase_executor = create_purchase_assistant_components(container)
    nfe_entry_executor = None
    if nfe_entry_service is not None and nfe_import_service is not None:
        nfe_entry_executor = NabiCodeNFeEntryAssistantGateway(
            nfe_entry_service, nfe_import_service
        )

    def runtime_factory():
        return LocalLlamaServer(
            runtime_manifest=LLAMA_CPP_B10537_CPU_X64,
            runtime_directory=ia_root / "runtime" / "b10537",
            manifest=QWEN3_1_7B_Q4_K_M_CANDIDATE,
            model_directory=ia_root / "models",
            log_directory=ia_root / "logs",
        )

    def assistant_factory(model, session_id):
        return create_draft_assistant(
            model=model,
            query_service=container.query,
            security_service=security,
            audit_service=audit,
            session_id=session_id,
            purchase_draft_service=purchase_drafts,
            purchase_executor=purchase_executor,
            nfe_entry_draft_service=nfe_entry_service,
            nfe_entry_executor=nfe_entry_executor,
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
    from licensing.restricted_commands import handle_restricted_command

    restricted_result = handle_restricted_command(list(argv or sys.argv)[1:], profile)
    if restricted_result is not None:
        return restricted_result
    license_gate = evaluate_runtime_gate(profile.app_dir)
    if not license_gate.allows(Capability.QT):
        QMessageBox.warning(
            None, "Licença NabiCode V2",
            startup_block_message(license_gate, Capability.QT),
        )
        return 3
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
        nfe_import_service = NFeImportService(NFeImportRepository(database))
        nfe_entry_service = NFeEntryDraftService(nfe_import_service)
        assistant_activation = _create_assistant_activation(
            database, profile, container, nfe_entry_service, nfe_import_service
        )
        qt.aboutToQuit.connect(assistant_activation.stop)
        license_timer = QTimer(qt)
        license_timer.setInterval(60_000)

        def monitor_license() -> None:
            current_gate = evaluate_runtime_gate(profile.app_dir)
            if current_gate.allows(Capability.QT):
                return
            license_timer.stop()
            QMessageBox.warning(
                None, "Licença NabiCode V2",
                startup_block_message(current_gate, Capability.QT),
            )
            qt.quit()

        license_timer.timeout.connect(monitor_license)
        license_timer.start()
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
            nfe_entry_service=nfe_entry_service,
        )
    except Exception as error:
        QMessageBox.critical(None, "NabiCode", str(error) or "Não foi possível iniciar o PDV Qt.")
        return 1
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
