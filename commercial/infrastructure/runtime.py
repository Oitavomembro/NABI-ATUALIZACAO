from __future__ import annotations

from database import DatabaseManager
from repositories import (
    CadastroAuxiliarRepository, CategoriaRepository, ClienteRepository,
    EstoqueRepository, ProdutoRepository,
)
from repositories.system_repository import SystemRepository
from repositories.financeiro_repository import FinanceiroRepository
from repositories.dashboard_repository import DashboardRepository
from services.cobranca_service import CobrancaService
from services.estoque_service import EstoqueService
from services.financeiro_service import FinanceiroService
from services.pdv_service import PDVService
from services.pdv_transaction_service import PDVTransactionService
from services.produto_service import ProdutoService
from services.customer_registration_service import CustomerRegistrationService

from .container import CommercialContainer


def create_commercial_container(database: DatabaseManager) -> CommercialContainer:
    """Compõe o backend comercial atual sem importar qualquer interface."""

    products = ProdutoService(
        ProdutoRepository(database),
        CategoriaRepository(database),
        CadastroAuxiliarRepository(database),
    )
    stock = EstoqueService(EstoqueRepository(database))
    finance_repository = FinanceiroRepository(database)
    finance = FinanceiroService(finance_repository)
    pdv = PDVService(database.connect)
    transaction = PDVTransactionService(
        database.connect,
        estoque_service=stock,
        financeiro_service=finance,
        pdv_service=pdv,
    )
    customers = ClienteRepository(database)
    system = SystemRepository(database.connect)
    registration = CustomerRegistrationService(
        customers,
        get_config=system.get_config,
        set_config=system.set_config,
        history_callback=system.add_client_history,
    )
    return CommercialContainer.from_existing(
        cliente_repository=customers,
        produto_service=products,
        pdv_transaction_service=transaction,
        pdv_service=pdv,
        financeiro_repository=finance_repository,
        cobranca_service=CobrancaService(database),
        dashboard_repository=DashboardRepository(database),
        customer_registration_service=registration,
        database=database,
        financeiro_service=finance,
    )
