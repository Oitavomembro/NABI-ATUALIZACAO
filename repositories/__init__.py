"""Repositórios do NabiCode."""

from .categoria_repository import CategoriaRepository
from .produto_repository import ProdutoRepository
from .cadastro_auxiliar_repository import CadastroAuxiliarRepository
from .nfe_import_repository import NFeImportRepository
from .nfe_devolucao_repository import NFeDevolucaoRepository
from .estoque_repository import EstoqueRepository
from .compra_repository import CompraRepository
from .cliente_repository import ClientePage, ClienteRepository, ClienteSuggestion
from .dashboard_repository import ClientSummary, DashboardIndicators, DayMovement, DayHistory, DashboardRepository
from .admin_audit_repository import AdminAuditRepository
from .emitted_document_repository import EmittedDocument, EmittedDocumentRepository
from .receipt_repository import ReceiptRepository

__all__ = ["CategoriaRepository", "ProdutoRepository", "CadastroAuxiliarRepository", "NFeImportRepository", "NFeDevolucaoRepository", "EstoqueRepository", "CompraRepository", "ClientePage", "ClienteRepository", "ClienteSuggestion", "ClientSummary", "DashboardIndicators", "DayMovement", "DayHistory", "DashboardRepository", "AdminAuditRepository", "EmittedDocument", "EmittedDocumentRepository", "ReceiptRepository", "ClientHistoryEntry", "SystemRepository", "ClientHistoryData", "ClientHistoryRepository", "CustomerMaintenanceRepository", "FornecedorRepository", "ProductsRepository", "CustomersRepository"]

from .financeiro_repository import FinanceiroRepository

from .system_repository import ClientHistoryEntry, SystemRepository

from .client_history_repository import ClientHistoryData, ClientHistoryRepository

from .customer_maintenance_repository import CustomerMaintenanceRepository
from .fornecedor_repository import FornecedorRepository

# Aliases em inglês para a camada modular, sem duplicar implementação.
ProductsRepository = ProdutoRepository
CustomersRepository = ClienteRepository
