from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from commercial.infrastructure.container import CommercialContainer
from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.customer_dto import (
    CustomerCreateCommand, CustomerReceiptCommand, CustomerUpdateCommand,
)
from commercial.domain.payments import Payment, PaymentMethod
from database import DatabaseManager
from database.schema_initializer import initialize_database
from repositories import (
    CadastroAuxiliarRepository,
    CategoriaRepository,
    ClienteRepository,
    EstoqueRepository,
    ProdutoRepository,
)
from repositories.financeiro_repository import FinanceiroRepository
from repositories.dashboard_repository import DashboardRepository
from repositories.system_repository import SystemRepository
from services.cobranca_service import CobrancaService
from services.customer_registration_service import CustomerRegistrationService
from services.estoque_service import EstoqueService
from services.financeiro_service import FinanceiroService
from services.pdv_service import PDVService
from services.pdv_transaction_service import PDVTransactionService
from services.produto_service import ProdutoService


class FailingEvents:
    def __init__(self) -> None:
        self.calls = 0

    def sale_committed(self, result) -> None:
        self.calls += 1
        raise RuntimeError("efeito secundário indisponível")


class CommercialSQLiteIntegrationTests(unittest.TestCase):
    SCHEMA_VERSION = 20

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database_path = self.root / "nabicode.db"
        self.database = DatabaseManager(self.database_path)
        initialize_database(
            db_name=str(self.database_path),
            backup_dir=str(self.root / "backups"),
            pdf_dir=str(self.root / "pdfs"),
            schema_version=self.SCHEMA_VERSION,
            last_database_update={
                "executada": False,
                "de": 0,
                "para": self.SCHEMA_VERSION,
                "backup": "",
            },
            network_mode=False,
            network_role="local",
            connect=self.database.connect,
            read_existing_version=lambda: 0,
            backup_before_update=lambda _source, _target: "",
        )
        with self.database.session(write=True) as connection:
            connection.execute("DELETE FROM historico_clientes")
            connection.execute("DELETE FROM clientes")

        self.customers = ClienteRepository(self.database)
        self.products = ProdutoService(
            ProdutoRepository(self.database),
            CategoriaRepository(self.database),
            CadastroAuxiliarRepository(self.database),
        )
        self.stock = EstoqueService(EstoqueRepository(self.database))
        self.finance_repository = FinanceiroRepository(self.database)
        self.finance = FinanceiroService(self.finance_repository)
        self.pdv = PDVService(self.database.connect)
        self.transaction = PDVTransactionService(
            self.database.connect,
            estoque_service=self.stock,
            financeiro_service=self.finance,
            pdv_service=self.pdv,
        )
        system = SystemRepository(self.database.connect)
        self.registration = CustomerRegistrationService(
            self.customers, get_config=system.get_config, set_config=system.set_config,
            history_callback=system.add_client_history,
        )
        self.container = CommercialContainer.from_existing(
            cliente_repository=self.customers,
            produto_service=self.products,
            pdv_transaction_service=self.transaction,
            pdv_service=self.pdv,
            financeiro_repository=self.finance_repository,
            cobranca_service=CobrancaService(self.database),
            dashboard_repository=DashboardRepository(self.database),
            customer_registration_service=self.registration,
            database=self.database,
            financeiro_service=self.finance,
        )
        self.application = self.container.application
        self.customer_id = self._create_customer("C100", "CLIENTE TESTE", 100, 500, 0)
        self.product_id = self.products.salvar(
            codigo="P100",
            nome="PRODUTO TESTE",
            preco_venda=Decimal("50.00"),
            categoria_id=None,
            tipo_produto="MERCADORIA",
            estoque_atual=10,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _create_customer(self, code, name, record_number, limit, balance) -> int:
        with self.customers.transaction() as connection:
            return self.customers.criar(
                {
                    "codigo": code,
                    "numero_ficha": record_number,
                    "nome": name,
                    "cpf": "",
                    "rg": "",
                    "telefone": "",
                    "endereco": "",
                    "observacoes": "",
                    "limite": limit,
                    "saldo_devedor": balance,
                },
                connection=connection,
            )

    def _set_credit(self, *, limit, balance, customer_id=None) -> None:
        with self.database.session(write=True) as connection:
            connection.execute(
                "UPDATE clientes SET limite=?, saldo_devedor=? WHERE id=?",
                (limit, balance, int(customer_id or self.customer_id)),
            )

    def _new_session(self, customer_id=None):
        session = self.application.new_session()
        self.application.select_customer(session, int(customer_id or self.customer_id))
        return session

    def _credit_session(
        self,
        amount,
        *,
        customer_id=None,
        product=False,
        entrance=Decimal("0.00"),
        sale_total=None,
        installments=3,
    ):
        session = self._new_session(customer_id)
        total = Decimal(str(sale_total if sale_total is not None else amount))
        if product:
            self.application.add_product(session, self.product_id, quantity=total / Decimal("50"))
        else:
            self.application.add_loose_item(
                session,
                description="ITEM AVULSO",
                quantity=1,
                unit_price=total,
            )
        entrance_payments = (
            [Payment(PaymentMethod.PIX, Decimal(str(entrance)))]
            if Decimal(str(entrance)) > 0
            else []
        )
        due_dates = tuple(date(2026, 9 + index, 22) for index in range(installments))
        self.application.prepare_store_credit(
            session,
            entrance_payments=entrance_payments,
            financed_value=Decimal(str(amount)),
            due_dates=due_dates,
        )
        return session

    def _one(self, sql, parameters=()):
        row = self.database.fetch_one(sql, parameters)
        return row[0] if row is not None else None

    def _counts(self):
        return {
            table: self._one(f"SELECT COUNT(*) FROM {table}")
            for table in (
                "movimentacoes",
                "parcelas",
                "titulos_financeiros",
                "estoque_movimentacoes",
            )
        } | {
            "pagamentos": self._one(
                "SELECT COUNT(*) FROM configuracoes WHERE chave LIKE 'pdv_pagamentos_venda_%'"
            )
        }

    def _payment_payload(self, sale_id):
        raw = self._one(
            "SELECT valor FROM configuracoes WHERE chave=?",
            (f"pdv_pagamentos_venda_{int(sale_id)}",),
        )
        return json.loads(raw) if raw else None

    def test_a_venda_a_vista_com_item_avulso(self):
        session = self._new_session()
        self.application.add_loose_item(
            session, description="SERVIÇO AVULSO", quantity=2, unit_price=Decimal("25.00")
        )
        self.application.prepare_payments(
            session, [Payment(PaymentMethod.CASH, Decimal("50.00"))]
        )
        result = self.application.checkout(session, user="integracao")

        self.assertTrue(result.committed)
        movement = self.database.fetch_one(
            "SELECT cliente_id,valor_decimal,status_pagamento FROM movimentacoes WHERE id=?",
            (result.sale_id,),
        )
        self.assertEqual(tuple(movement), (self.customer_id, "50", "PAGO"))
        self.assertEqual(self._one("SELECT COUNT(*) FROM estoque_movimentacoes"), 0)
        self.assertEqual(
            Decimal(str(self._one("SELECT saldo_devedor FROM clientes WHERE id=?", (self.customer_id,)))),
            Decimal("0"),
        )
        self.assertEqual(self._payment_payload(result.sale_id)["pagamentos"][0]["forma"], "DINHEIRO")

    def test_b_venda_com_produto_baixa_estoque_e_persiste_pagamento(self):
        session = self._new_session()
        self.application.add_product(session, self.product_id, quantity=2)
        self.application.prepare_payments(
            session, [Payment(PaymentMethod.PIX, Decimal("100.00"))]
        )
        result = self.application.checkout(session, user="integracao")

        self.assertTrue(result.committed)
        self.assertEqual(Decimal(str(self._one("SELECT estoque_atual FROM produtos WHERE id=?", (self.product_id,)))), Decimal("8"))
        stock_movement = self.database.fetch_one(
            "SELECT produto_id,tipo,quantidade,origem,origem_id FROM estoque_movimentacoes"
        )
        self.assertEqual(stock_movement[0], self.product_id)
        self.assertEqual(stock_movement[1], "SAIDA")
        self.assertEqual(Decimal(str(stock_movement[2])), Decimal("-2"))
        self.assertEqual(stock_movement[3], "VENDA")
        self.assertEqual(str(stock_movement[4]), str(result.sale_id))
        self.assertEqual(self._payment_payload(result.sale_id)["pagamentos"][0]["forma"], "PIX")

    def test_c_crediario_dentro_limite_persiste_saldo_titulo_e_parcelas(self):
        self._set_credit(limit=500, balance=0)
        session = self._credit_session(300)
        result = self.application.checkout(session, user="integracao")

        self.assertTrue(result.committed)
        self.assertEqual(Decimal(str(self._one("SELECT saldo_devedor FROM clientes WHERE id=?", (self.customer_id,)))), Decimal("300"))
        self.assertEqual(Decimal(str(self._one("SELECT valor_original_decimal FROM titulos_financeiros WHERE origem_id=?", (str(result.sale_id),)))), Decimal("300"))
        self.assertEqual(Decimal(str(self._one("SELECT SUM(valor_parcela) FROM parcelas WHERE movimentacao_id=?", (result.sale_id,)))), Decimal("300"))
        self.assertEqual(self._one("SELECT status_pagamento FROM movimentacoes WHERE id=?", (result.sale_id,)), "PENDENTE")

    def test_d_acima_limite_rejeita_sem_persistencia_ou_mutacao(self):
        self._set_credit(limit=500, balance=400)
        session = self._credit_session(101, product=True)
        stock_before = self._one("SELECT estoque_atual FROM produtos WHERE id=?", (self.product_id,))
        result = self.application.checkout(session, user="integracao")

        self.assertFalse(result.committed)
        self.assertIn("Crédito disponível", result.message)
        self.assertEqual(self._counts(), {"movimentacoes": 0, "parcelas": 0, "titulos_financeiros": 0, "estoque_movimentacoes": 0, "pagamentos": 0})
        self.assertEqual(self._one("SELECT saldo_devedor FROM clientes WHERE id=?", (self.customer_id,)), 400)
        self.assertEqual(self._one("SELECT estoque_atual FROM produtos WHERE id=?", (self.product_id,)), stock_before)
        self.assertFalse(session.cart.is_empty)

    def test_e_exatamente_no_limite_aprova(self):
        self._set_credit(limit=500, balance=400)
        result = self.application.checkout(
            self._credit_session(100), user="integracao"
        )
        self.assertTrue(result.committed)
        self.assertEqual(self._one("SELECT saldo_devedor FROM clientes WHERE id=?", (self.customer_id,)), 500)

    def test_f_entrada_mais_crediario_usa_somente_financiado(self):
        self._set_credit(limit=500, balance=0)
        session = self._credit_session(300, entrance=1700, sale_total=2000)
        result = self.application.checkout(session, user="integracao")

        self.assertTrue(result.committed)
        self.assertEqual(self._one("SELECT saldo_devedor FROM clientes WHERE id=?", (self.customer_id,)), 300)
        self.assertEqual(Decimal(str(self._one("SELECT valor_original_decimal FROM titulos_financeiros WHERE origem_id=?", (str(result.sale_id),)))), Decimal("300"))
        self.assertEqual(Decimal(str(self._one("SELECT SUM(valor_parcela) FROM parcelas WHERE movimentacao_id=?", (result.sale_id,)))), Decimal("300"))
        payload = self._payment_payload(result.sale_id)
        self.assertEqual(payload["pagamentos"][0], {"forma": "PIX", "valor": "1700"})
        self.assertEqual(payload["pagamentos"][1]["valor"], "300")

    def test_g_consumidor_final_com_crediario_rejeita(self):
        final_customer_id = self.customers.get_or_create_final_consumer()
        session = self._credit_session(10, customer_id=final_customer_id)
        result = self.application.checkout(session, user="integracao")
        self.assertFalse(result.committed)
        self.assertIn("Consumidor Final", result.message)
        self.assertEqual(self._counts()["movimentacoes"], 0)

    def test_h_cliente_removido_antes_do_checkout_rejeita(self):
        session = self._credit_session(10)
        with self.database.session(write=True) as connection:
            connection.execute("DELETE FROM clientes WHERE id=?", (self.customer_id,))
        result = self.application.checkout(session, user="integracao")
        self.assertFalse(result.committed)
        self.assertIn("Cliente não encontrado", result.message)
        self.assertEqual(self._counts()["movimentacoes"], 0)
        self.assertFalse(session.cart.is_empty)

    def test_i_falha_tardia_forca_rollback_integral_e_preserva_sessao(self):
        self._set_credit(limit=500, balance=0)
        session = self._credit_session(300, product=True)
        with self.database.session(write=True) as connection:
            connection.execute(
                """CREATE TRIGGER falha_tardia_estoque
                   BEFORE INSERT ON estoque_movimentacoes
                   BEGIN SELECT RAISE(ABORT, 'falha tardia controlada'); END"""
            )
        result = self.application.checkout(session, user="integracao")

        self.assertFalse(result.committed)
        self.assertEqual(self._counts(), {"movimentacoes": 0, "parcelas": 0, "titulos_financeiros": 0, "estoque_movimentacoes": 0, "pagamentos": 0})
        self.assertEqual(self._one("SELECT saldo_devedor FROM clientes WHERE id=?", (self.customer_id,)), 0)
        self.assertEqual(self._one("SELECT estoque_atual FROM produtos WHERE id=?", (self.product_id,)), 10)
        self.assertFalse(session.cart.is_empty)
        self.assertEqual(session.customer_id, self.customer_id)

    def test_j_commit_com_evento_falho_permanece_unico_e_confirmado(self):
        events = FailingEvents()
        container = CommercialContainer.from_existing(
            cliente_repository=self.customers,
            produto_service=self.products,
            pdv_transaction_service=self.transaction,
            pdv_service=self.pdv,
            events=events,
        )
        session = container.application.new_session()
        container.application.select_customer(session, self.customer_id)
        container.application.add_loose_item(
            session, description="AVULSO", quantity=1, unit_price=Decimal("50.00")
        )
        container.application.prepare_payments(
            session, [Payment(PaymentMethod.CASH, Decimal("50.00"))]
        )
        result = container.application.checkout(session, user="integracao")

        self.assertTrue(result.committed)
        self.assertTrue(result.secondary_effect_failed)
        self.assertTrue(result.session_consumed)
        self.assertTrue(session.cart.is_empty)
        self.assertIn("Não finalize novamente", result.message)
        self.assertEqual(self._one("SELECT COUNT(*) FROM movimentacoes"), 1)
        self.assertEqual(events.calls, 1)

    def test_cancelamento_backend_real_reverte_estoque_saldo_parcelas_e_titulo(self):
        self._set_credit(limit=500, balance=0)
        result = self.application.checkout(
            self._credit_session(100, product=True), user="integracao"
        )
        self.assertTrue(result.committed)
        cancellation = self.container.actions.cancel_sale(
            result.sale_id,
            context=ActionContext("integracao", ActionOrigin.SYSTEM),
            confirmation_granted=True,
        )
        self.assertTrue(cancellation.committed)

        self.assertEqual(self._one("SELECT status_pagamento FROM movimentacoes WHERE id=?", (result.sale_id,)), "CANCELADO")
        self.assertEqual(self._one("SELECT saldo_devedor FROM clientes WHERE id=?", (self.customer_id,)), 0)
        self.assertEqual(self._one("SELECT estoque_atual FROM produtos WHERE id=?", (self.product_id,)), 10)
        self.assertEqual(self._one("SELECT COUNT(*) FROM parcelas WHERE movimentacao_id=? AND status='CANCELADO'", (result.sale_id,)), 3)
        self.assertEqual(self._one("SELECT status FROM titulos_financeiros WHERE origem_id=?", (str(result.sale_id),)), "CANCELADO")

    def test_query_service_real_lê_credito_vendas_canceladas_cobrancas_e_movimentos(self):
        self._set_credit(limit=500, balance=400)
        query = self.container.query
        self.assertIsNotNone(query)
        self.assertEqual(query.customer_credit(self.customer_id).available_credit, Decimal("100.00"))

        result = self.application.checkout(self._credit_session(100), user="integracao")
        self.assertTrue(result.committed)
        today = date.today()
        self.assertTrue(any(row.sale_id == result.sale_id for row in query.daily_sales(today)))
        self.assertTrue(any(row.movement_id == result.sale_id for row in query.daily_movements(today)))

        with self.database.session(write=True) as connection:
            connection.execute(
                "UPDATE parcelas SET vencimento='2000-01-01' WHERE movimentacao_id=?",
                (result.sale_id,),
            )
        self.assertTrue(any(row.customer_id == self.customer_id for row in query.overdue_charges()))
        self.assertIsInstance(query.daily_receipts(today), tuple)

        self.transaction.cancel_sale(result.sale_id, user="integracao")
        self.assertTrue(any(row.sale_id == result.sale_id for row in query.cancelled_sales(today)))

    def test_customer_application_cria_edita_e_monta_ficha_por_id(self):
        customer_app = self.container.customer_application
        created = customer_app.create_customer(CustomerCreateCommand(
            name="CLIENTE FASE SEIS", code="C600", record_number=600,
            phone="71999990000", address="RUA TESTE", notes="NOTA",
            credit_limit=Decimal("500.00"),
        ))
        self.assertGreater(created.customer_id, 0)
        self.assertEqual(created.available_credit, Decimal("500.00"))

        updated = customer_app.update_customer(CustomerUpdateCommand(
            customer_id=created.customer_id, name="CLIENTE FASE 6 EDITADO",
            code="C600", record_number=601, phone="71888880000",
            address="AVENIDA TESTE", notes="EDITADO", credit_limit=Decimal("600.00"),
        ))
        self.assertEqual(updated.customer_id, created.customer_id)
        self.assertEqual(updated.name, "CLIENTE FASE 6 EDITADO")
        self.assertEqual(updated.credit_limit, Decimal("600.00"))
        statement = customer_app.customer_statement(created.customer_id)
        self.assertEqual(statement.customer.customer_id, created.customer_id)
        self.assertFalse(statement.historical_running_balance_available)
        self.assertEqual(statement.entries, ())
        self.assertEqual(statement.pending_amount, Decimal("0.00"))
        self.assertEqual(statement.overdue_amount, Decimal("0.00"))

    def test_recebimento_parcial_integral_rollback_e_ficha_real(self):
        self._set_credit(limit=500, balance=0)
        sale = self.application.checkout(self._credit_session(300), user="integracao")
        self.assertTrue(sale.committed)
        context = ActionContext("caixa", ActionOrigin.UI)
        first = self.container.actions.receive_customer_payment(
            CustomerReceiptCommand(
                customer_id=self.customer_id, amount=Decimal("150"),
                payment_method="PIX", payment_date=date.today(),
            ),
            context=context, confirmation_granted=True,
        )
        self.assertTrue(first.committed)
        statement = self.container.query.customer_statement(self.customer_id)
        self.assertTrue(any(entry.movement_id == sale.sale_id and entry.debit == Decimal("300.00") for entry in statement.entries))
        self.assertEqual(statement.pending_amount, Decimal("150.00"))
        self.assertEqual(statement.receipts[0].amount, Decimal("150.00"))
        self.assertEqual(sum((item.open_amount for item in statement.installments), Decimal("0")), Decimal("150.00"))
        self.assertTrue(any(item.status == "PARCIAL" for item in statement.installments))

        before_movements = self._one("SELECT COUNT(*) FROM movimentacoes")
        refused = self.container.actions.receive_customer_payment(
            CustomerReceiptCommand(
                customer_id=self.customer_id, amount=Decimal("151"),
                payment_method="DINHEIRO", payment_date=date.today(),
            ), context=context, confirmation_granted=True,
        )
        self.assertFalse(refused.committed)
        self.assertEqual(self._one("SELECT saldo_devedor FROM clientes WHERE id=?", (self.customer_id,)), 150)
        self.assertEqual(self._one("SELECT COUNT(*) FROM movimentacoes"), before_movements)

        final = self.container.actions.receive_customer_payment(
            CustomerReceiptCommand(
                customer_id=self.customer_id, amount=Decimal("150"),
                payment_method="PIX", payment_date=date.today(),
            ), context=context, confirmation_granted=True,
        )
        self.assertTrue(final.committed)
        final_statement = self.container.query.customer_statement(self.customer_id)
        self.assertEqual(final_statement.pending_amount, Decimal("0.00"))
        self.assertEqual(final_statement.installments, ())
        self.assertEqual(len(final_statement.receipts), 2)

    def test_cobranca_vencida_e_cancelamento_nao_mantem_divida(self):
        self._set_credit(limit=500, balance=0)
        sale = self.application.checkout(self._credit_session(100), user="integracao")
        with self.database.session(write=True) as connection:
            connection.execute(
                "UPDATE parcelas SET vencimento='2000-01-01' WHERE movimentacao_id=?",
                (sale.sale_id,),
            )
        statement = self.container.query.customer_statement(self.customer_id)
        self.assertEqual(statement.overdue_amount, Decimal("100.00"))
        self.assertTrue(any(item.overdue for item in statement.installments))

        cancelled = self.container.actions.cancel_sale(
            sale.sale_id, context=ActionContext("gerente", ActionOrigin.UI),
            confirmation_granted=True,
        )
        self.assertTrue(cancelled.committed)
        after = self.container.query.customer_statement(self.customer_id)
        self.assertEqual(after.pending_amount, Decimal("0.00"))
        self.assertEqual(after.installments, ())
        self.assertEqual(after.overdue_amount, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
