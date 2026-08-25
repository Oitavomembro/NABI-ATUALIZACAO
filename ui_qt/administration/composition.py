from administration.dashboard_application_service import DashboardApplicationService
from administration.product_management_service import ProductManagementService
from administration.purchase_management_service import PurchaseManagementService
from administration.settings_application_service import SettingsApplicationService
from administration.audit_application_service import AuditApplicationService
from administration.user_application_service import UserAdministrationService
from commercial.application.cash_application_service import CashApplicationService
from commercial.application.report_application_service import ReportApplicationService
from commercial.application.accountant_center_service import AccountantCenterApplicationService
from commercial.application.accountant_delivery_service import AccountantDeliveryApplicationService
from commercial.infrastructure.accountant_delivery_gateway import LocalFolderAccountantDeliveryGateway
from commercial.infrastructure.report_gateway import NabiCodeReportGateway
from repositories.dashboard_repository import DashboardRepository
from repositories.fornecedor_repository import FornecedorRepository
from repositories.system_repository import SystemRepository
from services.backup_service import BackupService
from services.admin_audit_service import AdminAuditService
from services.cash_service import CashService
from services.report_service import ReportService
from services.accountant_monthly_package_service import AccountantMonthlyPackageService
from services.system_diagnostics import SystemDiagnostics
from services.printing_service import PrintingService
from ui_qt.commercial.cash_dialog import CashDialog
from ui_qt.commercial.customer_dialog import CustomerManagementDialog
from ui_qt.commercial.financial_dialog import FinancialDialog
from ui_qt.commercial.product_management_dialog import ProductManagementDialog
from ui_qt.commercial.purchase_dialog import PurchaseDialog
from ui_qt.commercial.report_dialog import ReportDialog
from ui_qt.commercial.accountant_center_dialog import AccountantCenterDialog
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
    accountant_center = AccountantCenterApplicationService(
        AccountantMonthlyPackageService(database.connect, fiscal_service=None), security,
    )
    delivery_gateway = LocalFolderAccountantDeliveryGateway(
        outbox_path=profile.paths.config / "entrega_contabil" / "outbox.sqlite3",
        spool_dir=profile.paths.config / "entrega_contabil" / "pacotes_imutaveis",
    )
    accountant_delivery = AccountantDeliveryApplicationService(delivery_gateway, security)
    modules.append(AdministrativeModule(
        "Central do Contador",
        "Gerar e entregar pacote mensal por ação humana",
        "",
        "relatorios",
        "generate",
        lambda p: AccountantCenterDialog(
            accountant_center, p,
            worker_pool=getattr(p.window(), "worker_pool", None) if p else None,
            delivery_application=accountant_delivery,
        ),
        "contador",
    ))
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
