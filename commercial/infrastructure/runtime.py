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
from services.emitted_document_service import EmittedDocumentService
from services.pdf_document_service import PDFDocumentService
from services.printing_service import PrintingService
from services.receipt_service import ReceiptService

from .container import CommercialContainer
from .sale_receipt_gateway import NabiCodeSaleReceiptGateway
from .budget_gateway import NabiCodeBudgetGateway
from .suspended_sale_gateway import NabiCodeSuspendedSaleGateway
from .daily_sales_gateway import NabiCodeDailySalesGateway


def create_commercial_container(database: DatabaseManager, *, pdf_dir=None) -> CommercialContainer:
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
    receipt_output = None
    budget_gateway = None
    daily_sales_gateway = None
    if pdf_dir is not None:
        documents = EmittedDocumentService(database.connect)
        receipt_output = NabiCodeSaleReceiptGateway(
            receipts=ReceiptService(database, config_getter=system.get_config),
            printing=PrintingService(system.get_config),
            pdf=PDFDocumentService(
                connection_factory=database.connect,
                config_getter=system.get_config,
                pdf_dir=pdf_dir,
                document_registrar=documents.register,
            ),
            config_getter=system.get_config,
            item_allocator=pdv.ratear_total_itens,
        )
        final_consumer_id = customers.get_or_create_final_consumer()
        budget_gateway = NabiCodeBudgetGateway(
            pdv=pdv,
            receipts=ReceiptService(database, config_getter=system.get_config),
            printing=PrintingService(system.get_config),
            pdf=PDFDocumentService(
                connection_factory=database.connect,
                config_getter=system.get_config,
                pdf_dir=pdf_dir,
            ),
            final_consumer_id=final_consumer_id,
            config_getter=system.get_config,
        )
        daily_sales_gateway = NabiCodeDailySalesGateway(
            transaction_service=transaction,
            receipts=ReceiptService(database, config_getter=system.get_config),
            printing=PrintingService(system.get_config),
            pdf=PDFDocumentService(
                connection_factory=database.connect,
                config_getter=system.get_config,
                pdf_dir=pdf_dir,
                document_registrar=documents.register,
            ),
            config_getter=system.get_config,
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
        estoque_service=stock,
        receipt_output=receipt_output,
        budgets=budget_gateway,
        budget_output=budget_gateway,
        suspended_sales=NabiCodeSuspendedSaleGateway(pdv),
        daily_sales=daily_sales_gateway,
    )
