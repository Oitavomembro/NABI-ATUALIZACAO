from administration.dashboard_application_service import DashboardApplicationService
from administration.product_management_service import ProductManagementService
from administration.purchase_management_service import PurchaseManagementService
from administration.settings_application_service import SettingsApplicationService
from administration.user_application_service import UserAdministrationService
from commercial.application.cash_application_service import CashApplicationService
from commercial.application.report_application_service import ReportApplicationService
from commercial.infrastructure.report_gateway import NabiCodeReportGateway
from repositories.dashboard_repository import DashboardRepository
from repositories.fornecedor_repository import FornecedorRepository
from repositories.system_repository import SystemRepository
from services.backup_service import BackupService
from services.cash_service import CashService
from services.report_service import ReportService
from services.system_diagnostics import SystemDiagnostics
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

def _username(security):
    if security.session is None or security.is_expired():raise PermissionError("Sessão expirada. Entre novamente.")
    return security.session.user.username

def build_administrative_modules(
    container, database, profile, security, *, terminal="CAIXA-1",
    app_version="2.5.1", schema_version=21,
):
    modules=[];dashboard=DashboardApplicationService(DashboardRepository(database),security)
    modules.append(AdministrativeModule("Início","Resumo e movimentações do dia","F1","dashboard","view",lambda p:DashboardDialog(dashboard,p)))
    if getattr(container,"customer_application",None):modules.append(AdministrativeModule("Clientes","Cadastro, busca, edição e fichas","F3","clientes","view",lambda p:CustomerManagementDialog(container.customer_application,parent=p)))
    if getattr(container,"product_application",None) and getattr(container,"stock_actions",None):
        service=ProductManagementService(container.product_application,container.stock_actions,security);modules.append(AdministrativeModule("Produtos / Estoque","Cadastro, preços, saldos e histórico","F4","produtos","view",lambda p:ProductManagementDialog(service,p)))
    if getattr(container,"purchase_service",None):
        service=PurchaseManagementService(container.purchase_service,FornecedorRepository(database),security);modules.append(AdministrativeModule("Fornecedores / Compras","Pedidos, fornecedores e recebimentos","F5","compras","view",lambda p:PurchaseDialog(service,p)))
    cash=CashService(database.connect);modules.append(AdministrativeModule("Caixa","Abertura, movimentos e fechamento","F6","financeiro","view",lambda p:CashDialog(CashApplicationService(cash,terminal=terminal,user=_username(security)),p)))
    if getattr(container,"financial_query",None) and getattr(container,"financial_actions",None):modules.append(AdministrativeModule("Financeiro","Contas a receber, pagar e baixas","F7","financeiro","view",lambda p:FinancialDialog(container.financial_query,container.financial_actions,user=_username(security),parent=p)))
    reports=ReportApplicationService(NabiCodeReportGateway(ReportService(database.connect,output_dir=profile.paths.pdfs/"relatorios",authorize=lambda _a,_r:security.require("relatorios","generate"))))
    modules.append(AdministrativeModule("Relatórios","Indicadores, consultas e exportações","F8","relatorios","view",lambda p:ReportDialog(reports,_username(security),p)))
    users=UserAdministrationService(security);modules.append(AdministrativeModule("Usuários","Contas, perfis e controle de acesso","Ctrl+U","technical","users",lambda p:UsersDialog(users,p)))
    system = SystemRepository(database.connect)
    backups = BackupService(
        database_path=database.database_path,
        default_directory=profile.paths.backups,
        get_config=system.get_config,
        set_config=system.set_config,
        fiscal_directory=None,
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
    )
    modules.append(AdministrativeModule(
        "Configurações", "Interface, backup e diagnóstico", "Ctrl+G",
        "configs", "view", lambda p: SettingsDialog(settings, p),
    ))
    return tuple(modules)
