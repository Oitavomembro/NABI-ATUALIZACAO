import sqlite3
from datetime import datetime
from pathlib import Path

from administration.dashboard_application_service import DashboardApplicationService
from administration.product_management_service import ProductManagementService
from administration.purchase_management_service import PurchaseManagementService
from administration.settings_application_service import SettingsApplicationService
from administration.audit_application_service import AuditApplicationService
from administration.user_application_service import UserAdministrationService
from commercial.application.cash_application_service import CashApplicationService
from commercial.application.report_application_service import ReportApplicationService
from commercial.infrastructure.report_gateway import NabiCodeReportGateway
from repositories.dashboard_repository import DashboardRepository
from repositories.fornecedor_repository import FornecedorRepository
from repositories.system_repository import SystemRepository
from services.backup_service import BackupService
from services.admin_audit_service import AdminAuditService
from services.cash_service import CashService
from services.report_service import ReportService
from services.system_diagnostics import SystemDiagnostics
from services.printing_service import PrintingService
from services.help_center_service import HelpCenterDiagnosticService
from services.help_center_repair_service import (
    GreenRepairService, VisualPreferencesCallbacks,
)
from services.ui_preferences import UIPreferencesService
from ui_qt.commercial.cash_dialog import CashDialog
from ui_qt.commercial.customer_dialog import CustomerManagementDialog
from ui_qt.commercial.financial_dialog import FinancialDialog
from ui_qt.commercial.product_management_dialog import ProductManagementDialog
from ui_qt.commercial.purchase_dialog import PurchaseDialog
from ui_qt.commercial.report_dialog import ReportDialog
from .dashboard_dialog import DashboardDialog
from .module_hub import AdministrativeModule
from .users_dialog import UsersDialog
from .settings_dialog import SettingsDialog
from .help_dialog import HelpDialog
from .help_center_dialog import HelpCenterDialog
from .audit_dialog import AuditDialog

def _username(security):
    if security.session is None or security.is_expired():raise PermissionError("Sessão expirada. Entre novamente.")
    return security.session.user.username

def _database_probe(database):
    path = database.database_path.resolve()
    if not path.is_file():
        return {"state": "FALHA", "message": "Banco não encontrado"}
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        result = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        return {
            "state": "SAUDAVEL" if result == "ok" else "FALHA",
            "message": "Verificação somente leitura concluída" if result == "ok" else "Integridade requer atenção",
            "technical_id": f"quick_check:{result}",
        }
    finally:
        connection.close()

def _backup_probe(backups):
    candidates = []
    for directory in backups.configured_directories():
        folder = Path(directory)
        if folder.is_dir():
            candidates.extend(
                item for item in folder.iterdir()
                if item.is_file() and item.suffix.casefold() in {".db", ".nabibackup"}
            )
    if not candidates:
        return {"state": "ALERTA", "message": "Nenhum backup localizado nos destinos configurados"}
    latest = max(candidates, key=lambda item: item.stat().st_mtime)
    age = max(0, (datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)).days)
    return {
        "state": "SAUDAVEL" if age <= 1 else "ALERTA",
        "message": f"Backup mais recente há {age} dia(s)",
        "technical_id": f"backup_age_days:{age}",
    }

def _printer_probe(printing):
    available = len(printing.list_printers()) > 1
    return {
        "state": "SAUDAVEL" if available else "ALERTA",
        "message": "Impressora detectada" if available else "Somente impressora padrão/virtual disponível",
    }

def _visual_preferences_port(settings):
    return VisualPreferencesCallbacks(
        snapshot=lambda: dict(settings.snapshot_preferences_for_repair()),
        is_valid=lambda values: dict(values) == UIPreferencesService.normalize(values),
        normalize=UIPreferencesService.normalize,
        replace=lambda values: settings.replace_preferences_for_repair(dict(values)),
    )

def _repair_audit(audit_service, security, event):
    username = _username(security)
    if not security.require("configs", "edit"):
        raise PermissionError("Seu perfil não pode executar autorreparos VERDES.")
    security.touch()
    audit_service.record_event_strict(
        "SOCORRO",
        "AUTORREPARO_VERDE",
        object_id=event.operation_fingerprint,
        details=(
            f"repair={event.repair.value};phase={event.phase.value};"
            f"outcome={event.outcome.value};changed={int(event.changed)};"
            f"technical_id={event.technical_id}"
        ),
        result=event.outcome.value,
        user=username,
    )

def build_administrative_modules(
    container, database, profile, security, *, terminal="CAIXA-1",
    app_version="2.5.1", schema_version=21,
):
    modules=[];dashboard_repository=DashboardRepository(database);dashboard=DashboardApplicationService(dashboard_repository,security)
    modules.append(AdministrativeModule("Início","Resumo e movimentações do dia","F1","dashboard","view",lambda p:DashboardDialog(dashboard,p),"dashboard",lambda p:DashboardDialog(dashboard,p,embedded=True,worker_pool=getattr(p.window(),"worker_pool",None)),dashboard.load_client_summary))
    if getattr(container,"customer_application",None):
        def filtered_customers(parent, segment, title):
            def provider(term, limit):
                ids = dashboard_repository.client_segment_ids(segment, term, limit=limit)
                return container.customer_application.list_customers_by_ids(ids)
            return CustomerManagementDialog(
                container.customer_application, parent=parent,
                customer_provider=provider, filter_title=title,
            )
        modules.append(AdministrativeModule(
            "Clientes", "Cadastro, busca, edição e fichas", "F3", "clientes", "view",
            lambda p:CustomerManagementDialog(container.customer_application,parent=p),
            "clientes", filtered_factory=filtered_customers,
        ))
    if getattr(container,"product_application",None) and getattr(container,"stock_actions",None):
        product_management=ProductManagementService(container.product_application,container.stock_actions,security);modules.append(AdministrativeModule("Produtos / Estoque","Cadastro, preços, saldos e histórico","F4","produtos","view",lambda p, service=product_management:ProductManagementDialog(service,p),"produtos"))
    if getattr(container,"purchase_service",None):
        purchase_management=PurchaseManagementService(container.purchase_service,FornecedorRepository(database),security);modules.append(AdministrativeModule("Fornecedores / Compras","Pedidos, fornecedores e recebimentos","","compras","view",lambda p, service=purchase_management:PurchaseDialog(service,p),"compras"))
    cash=CashService(database.connect);modules.append(AdministrativeModule("Caixa","Abertura, movimentos e fechamento","","financeiro","view",lambda p:CashDialog(CashApplicationService(cash,terminal=terminal,user=_username(security)),p),"caixa"))
    if getattr(container,"financial_query",None) and getattr(container,"financial_actions",None):modules.append(AdministrativeModule("Financeiro","Contas a receber, pagar e baixas","","financeiro","view",lambda p:FinancialDialog(container.financial_query,container.financial_actions,user=_username(security),parent=p),"financeiro"))
    reports=ReportApplicationService(NabiCodeReportGateway(ReportService(database.connect,output_dir=profile.paths.pdfs/"relatorios",authorize=lambda _a,_r:security.require("relatorios","generate"))))
    modules.append(AdministrativeModule("Relatórios","Indicadores, consultas e exportações","","relatorios","view",lambda p:ReportDialog(reports,_username(security),p),"relatorios"))
    users=UserAdministrationService(security);modules.append(AdministrativeModule("Usuários","Contas, perfis e controle de acesso","Ctrl+U","technical","users",lambda p:UsersDialog(users,p),"usuarios"))
    system = SystemRepository(database.connect)
    backups = BackupService(
        database_path=database.database_path,
        default_directory=profile.paths.backups,
        get_config=system.get_config,
        set_config=system.set_config,
        fiscal_directory=profile.paths.fiscal,
    )
    diagnostics = SystemDiagnostics(
        database,
        app_dir=profile.app_dir,
        backup_dir=profile.paths.backups,
        rollback_dir=profile.paths.rollback,
        diagnostic_dir=profile.paths.diagnostics,
        app_version=app_version,
        schema_version=schema_version,
        required_tables=("configuracoes", "clientes", "produtos", "movimentacoes"),
    )
    settings = SettingsApplicationService(
        security=security,
        system_repository=system,
        config_path=profile.paths.config / "sistema.json",
        backup_service=backups,
        diagnostics=diagnostics,
        printing_service=PrintingService(system.get_config),
    )
    modules.append(AdministrativeModule(
        "Configurações", "Interface, backup e diagnóstico", "Ctrl+G",
        "configs", "view", lambda p: SettingsDialog(settings, p), "configs",
    ))
    modules.append(AdministrativeModule(
        "Ajuda", "Atalhos e orientação dos módulos", "Ctrl+H",
        "dashboard", "view", lambda p: HelpDialog(parent=p), "ajuda",
    ))
    audit_service = AdminAuditService(database.connect)
    printing = PrintingService(system.get_config)
    socorro = HelpCenterDiagnosticService(
        persistent_dirs=(profile.paths.backups, profile.paths.rollback, profile.paths.diagnostics),
        database_probe=lambda: _database_probe(database),
        backup_probe=lambda: _backup_probe(backups),
        printer_probe=lambda: _printer_probe(printing),
        nabi_probe=None,
        audit=lambda module, action, object_id, details, result, user: audit_service.record_event(
            module, action, object_id=object_id, details=details, result=result, user=user,
        ),
    )
    green_repairs = GreenRepairService(
        audit=lambda event: _repair_audit(audit_service, security, event),
        visual_preferences=_visual_preferences_port(settings),
    )
    modules.append(AdministrativeModule(
        "Central de Socorro", "Diagnóstico seguro e relatório para suporte", "Ctrl+F1",
        "configs", "view",
        lambda p: HelpCenterDialog(socorro, p, repair_service=green_repairs),
        "socorro",
    ))
    audit = AuditApplicationService(audit_service, security)
    modules.append(AdministrativeModule(
        "Auditoria", "Histórico de login e segurança", "Ctrl+L",
        "technical", "audit", lambda p: AuditDialog(audit, p), "auditoria",
    ))
    return tuple(modules)
