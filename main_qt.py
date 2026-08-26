from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
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
    CustomerRegistrationDraftService,
    NabiCodeCustomerRegistrationGateway,
    CustomerReceiptDraftService,
    NabiCodeCustomerReceiptAssistantGateway,
    NabiCodeProcurementAssistantGateway,
    NabiCodeProductStockAssistantGateway,
    ProductStockDraftService,
    PurchaseOrderDraftService,
    SupplierRegistrationDraftService,
    create_financial_assistant_components,
)
from administration.product_management_service import ProductManagementService
from commercial.infrastructure.runtime import create_commercial_container
from commercial.application.report_application_service import ReportApplicationService
from commercial.application.cash_application_service import CashApplicationService
from assistant_nabi.cash_drafts import CashDraftService
from assistant_nabi.cash_gateway import NabiCodeCashAssistantGateway
from commercial.infrastructure.report_gateway import NabiCodeReportGateway
from core.app_version import load_app_version
from core.runtime_profile import DatabaseUsageLock, configure_profile_environment
from core.qt_startup_splash import QtStartupSplash
from database import DatabaseManager
from database.schema_initializer import initialize_database
from database.sqlite_connection import backup_database
from services.network_config_service import NetworkConfigService, NetworkPaths
from services.admin_audit_service import AdminAuditService
from services.security_service import SecurityService
from services.report_service import ReportService
from services.cash_service import CashService
from services.backup_service import BackupService
from services.fiscal_service import FiscalService
from services.fiscal_catalog_readiness_service import FiscalCatalogReadinessService
from services.assisted_product_stock_service import AssistedProductStockService
from repositories.system_repository import SystemRepository
from repositories.fornecedor_repository import FornecedorRepository
from administration.purchase_management_service import PurchaseManagementService
from repositories import NFeImportRepository
from services import NFeImportService
from ui_qt.app import run_shell
from ui_qt.administration import (
    AdministrativeModuleHub, ApplicationLoginDialog, InitialSetupDialog,
    LegacySecurityMigrationDialog,
    build_administrative_modules,
)
from licensing.gate import Capability, LicenseGate
from licensing.activation_dialog import LicenseActivationDialog
from licensing.runtime import (
    build_runtime_license_service, evaluate_runtime_gate, startup_block_message,
)

SCHEMA_VERSION = 21


def _administrative_hub_factory(security, modules):
    def create(parent):
        if security.session is None or security.is_expired():
            if ApplicationLoginDialog(security, parent).exec() != QDialog.DialogCode.Accepted:
                raise PermissionError("Autenticação cancelada. Os módulos permanecem bloqueados.")
        return AdministrativeModuleHub(security, modules, parent)
    return create


def _create_assistant_activation(
    database, profile, container, nfe_entry_service=None, nfe_import_service=None,
    security=None,
):
    """Compõe ativação autenticada; nenhum runtime inicia durante o startup."""

    system = SystemRepository(database.connect)
    owns_security = security is None
    if owns_security:
        security = SecurityService(database.connect)
        security.bootstrap_admin(system.get_config("admin_senha_hash"))
    audit = AdminAuditService(database.connect, logging.getLogger("NabiCode.NabiAudit"))
    ia_root = profile.app_dir / "ia"
    purchase_drafts = purchase_executor = None
    purchase_query_service = None
    supplier_drafts = purchase_order_drafts = procurement_executor = None
    if getattr(container, "purchase_service", None) is not None:
        purchase_drafts, purchase_executor = create_purchase_assistant_components(container)
        purchase_query_service = PurchaseManagementService(
            container.purchase_service, FornecedorRepository(database), security
        )
        supplier_drafts = SupplierRegistrationDraftService()
        purchase_order_drafts = PurchaseOrderDraftService(purchase_query_service)
        procurement_executor = NabiCodeProcurementAssistantGateway(
            purchase_query_service
        )
    product_stock_drafts = product_stock_executor = None
    if all(getattr(container, name, None) is not None for name in (
        "product_application", "stock_actions", "product_service", "stock_service"
    )):
        assisted_stock = AssistedProductStockService(
            container.product_service, container.stock_service
        )
        product_management = ProductManagementService(
            container.product_application, container.stock_actions, security,
            assisted_stock,
        )
        product_stock_drafts = ProductStockDraftService(product_management)
        product_stock_executor = NabiCodeProductStockAssistantGateway(
            product_management
        )
    nfe_entry_executor = None
    if nfe_entry_service is not None and nfe_import_service is not None:
        nfe_entry_executor = NabiCodeNFeEntryAssistantGateway(
            nfe_entry_service, nfe_import_service
        )
    customer_drafts = customer_executor = None
    customer_application = getattr(container, "customer_application", None)
    if customer_application is not None:
        customer_drafts = CustomerRegistrationDraftService(customer_application)
        customer_executor = NabiCodeCustomerRegistrationGateway(customer_application)
    customer_receipt_drafts = customer_receipt_executor = None
    if customer_application is not None and getattr(container, "actions", None) is not None:
        customer_receipt_drafts = CustomerReceiptDraftService(customer_application)
        customer_receipt_executor = NabiCodeCustomerReceiptAssistantGateway(
            container.actions, customer_application
        )
    financial_drafts = financial_executor = None
    if (
        getattr(container, "financial_actions", None) is not None
        and getattr(container, "finance_service", None) is not None
    ):
        financial_drafts, financial_executor = create_financial_assistant_components(
            container, container.finance_service
        )
    profile_paths = getattr(profile, "paths", None)
    report_output = getattr(profile_paths, "pdfs", profile.app_dir / "pdfs")
    report_service = ReportApplicationService(NabiCodeReportGateway(ReportService(
        database.connect,
        output_dir=report_output / "relatorios",
        authorize=lambda _action, _report: security.require("relatorios", "view"),
    )))
    terminal = str(system.get_config("caixa_terminal") or "CAIXA-1")

    def cash_service_factory(actor):
        return CashApplicationService(
            CashService(database.connect), terminal=terminal, user=actor.username
        )

    def runtime_factory():
        return LocalLlamaServer(
            runtime_manifest=LLAMA_CPP_B10537_CPU_X64,
            runtime_directory=ia_root / "runtime" / "b10537",
            manifest=QWEN3_1_7B_Q4_K_M_CANDIDATE,
            model_directory=ia_root / "models",
            log_directory=ia_root / "logs",
        )

    def assistant_factory(model, session_id, authenticated_session):
        actor = getattr(authenticated_session, "user", None)
        cash_drafts = cash_executor = None
        if actor is not None and getattr(actor, "active", False):
            cash_application = cash_service_factory(actor)
            cash_drafts = CashDraftService(cash_application)
            cash_executor = NabiCodeCashAssistantGateway(cash_application)
        return create_draft_assistant(
            model=model,
            query_service=container.query,
            financial_query_service=getattr(container, "financial_query", None),
            report_service=report_service,
            cash_service_factory=cash_service_factory,
            cash_draft_service=cash_drafts,
            cash_executor=cash_executor,
            security_service=security,
            audit_service=audit,
            session_id=session_id,
            purchase_draft_service=purchase_drafts,
            purchase_executor=purchase_executor,
            purchase_query_service=purchase_query_service,
            supplier_draft_service=supplier_drafts,
            purchase_order_draft_service=purchase_order_drafts,
            procurement_executor=procurement_executor,
            product_stock_draft_service=product_stock_drafts,
            product_stock_executor=product_stock_executor,
            financial_draft_service=financial_drafts,
            financial_executor=financial_executor,
            nfe_entry_draft_service=nfe_entry_service,
            nfe_entry_executor=nfe_entry_executor,
            customer_draft_service=customer_drafts,
            customer_executor=customer_executor,
            customer_receipt_draft_service=customer_receipt_drafts,
            customer_receipt_executor=customer_receipt_executor,
        )

    return AuthenticatedAssistantActivation(
        security_service=security,
        runtime_factory=runtime_factory,
        assistant_factory=assistant_factory,
        logout_on_stop=owns_security,
    )


def _create_licensed_assistant(
    database, profile, container, license_gate, security=None
):
    """Compõe a Nabi para edições operacionais e isola o apoio fiscal."""

    assistant_enabled = any(
        license_gate.allows(capability)
        for capability in (
            Capability.ASSISTANT,
            Capability.COMMERCIAL_WRITE,
            Capability.FISCAL_WRITE,
        )
    )
    if not assistant_enabled:
        return None, None, None
    nfe_import_service = nfe_entry_service = None
    if license_gate.allows(Capability.FISCAL_WRITE):
        import_security = ({
            "actor_provider": (
                lambda: (
                    security.session.user.username
                    if security is not None
                    and security.session is not None
                    and not security.is_expired()
                    and security.session.user.active
                    else None
                )
            ),
            "authorization_provider": (
                lambda module, action: security.require(module, action)
            ),
        } if security is not None else {})
        nfe_import_service = NFeImportService(
            NFeImportRepository(database), **import_security
        )
        nfe_entry_service = NFeEntryDraftService(nfe_import_service)
    activation_args = ({"security": security} if security is not None else {})
    activation = _create_assistant_activation(
        database, profile, container, nfe_entry_service, nfe_import_service,
        **activation_args,
    )
    unavailable = UnavailableAssistantService(
        "Clique em Ativar Nabi e autentique um usuário autorizado. "
        "O modelo local somente será iniciado depois da validação."
    )
    return unavailable, activation, nfe_entry_service


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


def _initialize(database: DatabaseManager, profile, network_mode: bool, network_role: str) -> bool:
    last_update = {"executada": False, "de": 0, "para": SCHEMA_VERSION, "backup": ""}

    def backup_before_update(previous: int, target: int) -> str:
        profile.paths.backups.mkdir(parents=True, exist_ok=True)
        destination = profile.paths.backups / (
            f"pre_qt_schema_{previous}_{target}_{datetime.now():%Y%m%d_%H%M%S}.db"
        )
        backup_database(database.database_path, destination, network_mode=network_mode)
        return str(destination)

    return bool(initialize_database(
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
    ))


def main(argv=None) -> int:
    effective_argv = list(argv if argv is not None else sys.argv)
    if "--apply-prepared-restore" in effective_argv:
        from services.database_restore_helper import main as restore_main
        index = effective_argv.index("--apply-prepared-restore")
        return restore_main(effective_argv[index + 1:])
    qt = QApplication.instance() or QApplication(effective_argv)
    profile = configure_profile_environment("PRODUCAO")
    from licensing.restricted_commands import handle_restricted_command

    restricted_result = handle_restricted_command(list(argv or sys.argv)[1:], profile)
    if restricted_result is not None:
        return restricted_result
    license_gate = evaluate_runtime_gate(profile.app_dir)
    if not license_gate.allows(Capability.QT):
        license_service = build_runtime_license_service(profile.app_dir)
        activation = LicenseActivationDialog(
            license_service, license_gate.decision
        )
        if activation.exec() != QDialog.DialogCode.Accepted:
            return 3
        license_gate = LicenseGate(license_service.evaluate())
        if not license_gate.allows(Capability.QT):
            return 3
    configuration = _network_configuration(profile)
    database_path = profile.validate_database(
        configuration.get("db_path") or profile.paths.database
    )
    network_mode = configuration.get("modo") == "rede"
    network_role = str(configuration.get("papel") or "local")
    lock = DatabaseUsageLock(database_path, f"{profile.profile}-QT")
    splash = QtStartupSplash()
    try:
        lock.acquire()
        database = DatabaseManager(database_path, network_mode=network_mode, logger=logging.getLogger("NabiCode.Qt"))
        first_install = _initialize(database, profile, network_mode, network_role)
        container = create_commercial_container(database, pdf_dir=profile.paths.pdfs)
        system = SystemRepository(database.connect)
        module_security = SecurityService(database.connect)
        # O splash canônico cobre a preparação real e sai antes do primeiro
        # diálogo obrigatório, exatamente como no fluxo do Legacy.
        splash.close()
        if first_install:
            if module_security.has_users():
                raise RuntimeError("O banco novo já possui usuário; configuração inicial recusada.")
            if InitialSetupDialog(module_security).exec() != QDialog.DialogCode.Accepted:
                return 5
        else:
            module_security.bootstrap_admin(system.get_config("admin_senha_hash"))
            if module_security.needs_existing_installation_migration():
                if LegacySecurityMigrationDialog(module_security).exec() != QDialog.DialogCode.Accepted:
                    return 5
        if ApplicationLoginDialog(module_security).exec() != QDialog.DialogCode.Accepted:
            return 5
        fiscal_service = fiscal_catalog_service = nfe_purchase_import = None
        if license_gate.allows(Capability.FISCAL_WRITE):
            fiscal_service = FiscalService(
                database.connect,
                storage_dir=profile.paths.fiscal,
                actor_provider=lambda: (
                    module_security.session.user.username
                    if module_security.session is not None
                    and not module_security.is_expired()
                    and module_security.session.user.active
                    else None
                ),
                authorization_provider=lambda action: module_security.require("fiscal", action),
            )
            fiscal_catalog_service = FiscalCatalogReadinessService(database.connect)
            fiscal_service.bind_readiness_catalog(fiscal_catalog_service)
            import_security = {
                "actor_provider": lambda: (
                    module_security.session.user.username
                    if module_security.session is not None
                    and not module_security.is_expired()
                    and module_security.session.user.active else None
                ),
                "authorization_provider": lambda module, action: module_security.require(module, action),
            }
            purchase_imports = NFeImportService(NFeImportRepository(database), **import_security)
            from administration.nfe_purchase_import_service import NFePurchaseImportManagementService
            nfe_purchase_import = NFePurchaseImportManagementService(
                purchase_imports, module_security,
                company_document_provider=lambda: fiscal_service.load_config().get("cnpj", ""),
            )
        module_actions = build_administrative_modules(
            container, database, profile, module_security,
            terminal=str(system.get_config("caixa_terminal") or "CAIXA-1"),
            app_version=load_app_version("2.5.1", source_file=__file__),
            schema_version=SCHEMA_VERSION,
            fiscal_service=fiscal_service,
            fiscal_catalog_service=fiscal_catalog_service,
            nfe_purchase_import=nfe_purchase_import,
            restore_helper_command=lambda request, active, staging: (
                sys.executable,
                *(tuple() if getattr(sys, "frozen", False) else (str(Path(__file__).resolve()),)),
                "--apply-prepared-restore",
                "--request", str(request),
                "--database", str(active),
                "--staging-root", str(staging),
                "--parent-pid", str(os.getpid()),
            ),
        )
        daily_backup = BackupService(
            database_path=database.database_path,
            default_directory=profile.paths.backups,
            get_config=system.get_config,
            set_config=system.set_config,
            fiscal_directory=profile.paths.fiscal,
        )
        assistant_service, assistant_activation, nfe_entry_service = (
            _create_licensed_assistant(
                database, profile, container, license_gate,
                security=module_security,
            )
        )
        if assistant_activation is not None:
            qt.aboutToQuit.connect(assistant_activation.stop)
        initial_entitlements = (
            license_gate.allows(Capability.ASSISTANT),
            license_gate.allows(Capability.COMMERCIAL_WRITE),
            license_gate.allows(Capability.FISCAL_WRITE),
        )
        license_timer = QTimer(qt)
        license_timer.setInterval(60_000)

        def monitor_license() -> None:
            current_gate = evaluate_runtime_gate(profile.app_dir)
            current_entitlements = (
                current_gate.allows(Capability.ASSISTANT),
                current_gate.allows(Capability.COMMERCIAL_WRITE),
                current_gate.allows(Capability.FISCAL_WRITE),
            )
            if (
                current_gate.allows(Capability.QT)
                and current_entitlements == initial_entitlements
            ):
                return
            license_timer.stop()
            if assistant_activation is not None:
                assistant_activation.stop()
            message = (
                startup_block_message(current_gate, Capability.QT)
                if not current_gate.allows(Capability.QT)
                else (
                    "Os recursos assinados da licença foram alterados. "
                    "O NabiCode será fechado para reaplicar as travas com segurança."
                )
            )
            QMessageBox.warning(
                None, "Licença NabiCode V2",
                message,
            )
            qt.quit()

        license_timer.timeout.connect(monitor_license)
        license_timer.start()
        from core.config_manager import ConfigManager
        from services.ui_preferences import UIPreferencesService
        visual_config = ConfigManager(
            profile.paths.config / "sistema.json",
            {"interface": UIPreferencesService.DEFAULTS, "interface_usuarios": {}},
        )
        visual_users = visual_config.get("interface_usuarios", {})
        visual_key = UIPreferencesService.user_key(module_security.session.user.username)
        visual_values = (
            visual_users.get(visual_key)
            if isinstance(visual_users, dict) else None
        )
        if not isinstance(visual_values, dict):
            visual_values = visual_config.get("interface", {})
        return run_shell(
            container.application,
            module_security,
            module_actions,
            argv,
            store_name=str(system.get_config("nome_loja") or "NabiCode"),
            cash_label="Caixa ativo",
            profile_label=(
                f"{profile.label} • COMERCIAL / FISCAL"
                if license_gate.allows(Capability.FISCAL_WRITE)
                else f"{profile.label} • COMERCIAL / NÃO FISCAL"
            ),
            assistant_service=assistant_service,
            assistant_activation=assistant_activation,
            nfe_entry_service=nfe_entry_service,
            reauthenticate=lambda parent: (
                ApplicationLoginDialog(module_security, parent).exec()
                == QDialog.DialogCode.Accepted
            ),
            daily_backup_service=daily_backup,
            visual_preferences=UIPreferencesService.normalize(visual_values),
            auto_activate_assistant=license_gate.allows(Capability.ASSISTANT),
        )
    except Exception as error:
        splash.close()
        QMessageBox.critical(None, "NabiCode", str(error) or "Não foi possível iniciar o PDV Qt.")
        return 1
    finally:
        splash.close()
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
