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
from .audit_dialog import AuditDialog

def _username(security):
    if security.session is None or security.is_expired():raise PermissionError("Sessão expirada. Entre novamente.")
    return security.session.user.username

def build_administrative_modules(
    container, database, profile, security, *, terminal="CAIXA-1",
    app_version="2.5.1", schema_version=21,
):
    customer_application = getattr(container, "customer_application", None)
    financial_actions = getattr(container, "financial_actions", None)
    for service in (customer_application, financial_actions):
        bind = getattr(service, "bind_mutation_authorizer", None)
        if callable(bind):
            bind(security.require_actor)
    modules=[];dashboard=DashboardApplicationService(DashboardRepository(database),security)
    modules.append(AdministrativeModule("Início","Resumo e movimentações do dia","F1","dashboard","view",lambda p:DashboardDialog(dashboard,p),"dashboard",lambda p:DashboardDialog(dashboard,p,embedded=True,worker_pool=getattr(p.window(),"worker_pool",None)),dashboard.load_client_summary))
    if getattr(container,"customer_application",None):modules.append(AdministrativeModule("Clientes","Cadastro, busca, edição e fichas","F3","clientes","view",lambda p:CustomerManagementDialog(container.customer_application,parent=p),"clientes"))
    if getattr(container,"product_application",None) and getattr(container,"stock_actions",None):
        service=ProductManagementService(container.product_application,container.stock_actions,security);modules.append(AdministrativeModule("Produtos / Estoque","Cadastro, preços, saldos e histórico","F4","produtos","view",lambda p:ProductManagementDialog(service,p),"produtos"))
    if getattr(container,"purchase_service",None):
        service=PurchaseManagementService(container.purchase_service,FornecedorRepository(database),security);modules.append(AdministrativeModule("Fornecedores / Compras","Pedidos, fornecedores e recebimentos","","compras","view",lambda p:PurchaseDialog(service,p),"compras"))
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
    audit = AuditApplicationService(AdminAuditService(database.connect), security)
    modules.append(AdministrativeModule(
        "Auditoria", "Histórico de login e segurança", "Ctrl+L",
        "technical", "audit", lambda p: AuditDialog(audit, p), "auditoria",
    ))
    return tuple(modules)
