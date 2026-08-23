from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from commercial.application.action_dto import ActionContext, ActionOrigin, ActionSensitivity
from commercial.application.financial_dto import (
    CreateFinancialTitleCommand, SettleFinancialTitleCommand,
)
from commercial.infrastructure.runtime import create_commercial_container
from database import DatabaseManager
from database.schema_initializer import initialize_database


class FailingFinancialEvents:
    def financial_event(self, event):
        raise RuntimeError("consumer offline")


class CommercialFinancialServicesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = DatabaseManager(root / "nabicode.db")
        initialize_database(
            db_name=str(root / "nabicode.db"), backup_dir=str(root / "backups"),
            pdf_dir=str(root / "pdfs"), schema_version=20,
            last_database_update={"executada": False, "de": 0, "para": 20, "backup": ""},
            network_mode=False, network_role="local", connect=self.db.connect,
            read_existing_version=lambda: 0, backup_before_update=lambda *_: "",
        )
        self.container = create_commercial_container(self.db)
        self.query = self.container.financial_query
        self.actions = self.container.financial_actions
        self.context = ActionContext("financeiro-teste", ActionOrigin.UI)

    def tearDown(self):
        self.temp.cleanup()

    def _title(self, kind, amount="500.00", due=None):
        command = CreateFinancialTitleCommand(
            Decimal(amount), due or date.today(), party_name="PARTE TESTE",
            description=f"TITULO {kind}",
        )
        method = self.actions.create_receivable if kind == "RECEBER" else self.actions.create_payable
        result = method(command, context=self.context, confirmed=True)
        self.assertTrue(result.committed)
        return result.title_id

    def _settle(self, kind, title_id, amount, payment_date=None):
        command = SettleFinancialTitleCommand(
            title_id, Decimal(amount), "PIX", payment_date or date.today()
        )
        method = self.actions.settle_receivable if kind == "RECEBER" else self.actions.settle_payable
        return method(command, context=self.context, confirmed=True)

    def test_receber_e_pagar_ficam_separados_e_parciais(self):
        receivable_id = self._title("RECEBER")
        payable_id = self._title("PAGAR")

        first_receipt = self._settle("RECEBER", receivable_id, "200.00")
        first_payment = self._settle("PAGAR", payable_id, "200.00")
        self.assertEqual((first_receipt.status, first_receipt.open_amount), ("PARCIAL", Decimal("300.00")))
        self.assertEqual((first_payment.status, first_payment.open_amount), ("PARCIAL", Decimal("300.00")))
        self.assertEqual(self._settle("RECEBER", receivable_id, "300.00").status, "PAGO")
        self.assertEqual(self._settle("PAGAR", payable_id, "300.00").status, "PAGO")

        self.assertEqual({x.title_id for x in self.query.receivables()}, {receivable_id})
        self.assertEqual({x.title_id for x in self.query.payables()}, {payable_id})

    def test_vencimentos_cobranca_e_resumo_nao_misturam_conta_a_pagar(self):
        past = date.today() - timedelta(days=3)
        future = date.today() + timedelta(days=3)
        overdue_id = self._title("RECEBER", "120.00", past)
        self._title("RECEBER", "80.00", future)
        payable_id = self._title("PAGAR", "70.00", past)

        with self.db.session(write=True) as conn:
            customer_id = conn.execute(
                "INSERT INTO clientes(codigo,nome,telefone) VALUES('C7','CLIENTE COBRANCA','71999999999')"
            ).lastrowid
            movement_id = conn.execute(
                "INSERT INTO movimentacoes(cliente_id,tipo,descricao,valor,data,vencimento,status_pagamento,valor_aberto) VALUES(?,?,?,?,?,?,?,?)",
                (customer_id, "COMPRA", "VENDA CREDIARIO", 90, past.isoformat(), past.isoformat(), "PENDENTE", 90),
            ).lastrowid
            conn.execute(
                "INSERT INTO parcelas(movimentacao_id,numero_parcela,valor_parcela,vencimento,status,valor_pago,dados_confiaveis) VALUES(?,?,?,?,?,?,1)",
                (movement_id, 1, 90, past.isoformat(), "PENDENTE", 0),
            )

        self.assertEqual({x.title_id for x in self.query.overdue_receivables()}, {overdue_id})
        collections = self.query.customer_collections()
        self.assertEqual(len(collections), 1)
        self.assertEqual(collections[0].customer_id, customer_id)
        self.assertNotIn(payable_id, {x.installment_id for x in collections})
        summary = self.query.financial_summary(date.today(), date.today())
        self.assertEqual(summary.receivable_open, Decimal("200.00"))
        self.assertEqual(summary.receivable_overdue, Decimal("120.00"))
        self.assertEqual(summary.payable_open, Decimal("70.00"))

    def test_rollback_logico_cancelamento_e_estorno_individual(self):
        title_id = self._title("RECEBER", "500.00")
        rejected = self._settle("RECEBER", title_id, "501.00")
        self.assertFalse(rejected.committed)
        title = next(x for x in self.query.receivables() if x.title_id == title_id)
        self.assertEqual((title.received_amount, title.open_amount), (Decimal("0.00"), Decimal("500.00")))

        settled = self._settle("RECEBER", title_id, "200.00")
        reversed_result = self.actions.reverse_financial_payment(
            settled.payment_id, context=self.context, confirmed=True
        )
        self.assertTrue(reversed_result.committed)
        self.assertEqual(reversed_result.open_amount, Decimal("500.00"))
        cancelled = self.actions.cancel_financial_title(title_id, context=self.context, confirmed=True)
        self.assertEqual((cancelled.committed, cancelled.status), (True, "CANCELADO"))
        self.assertFalse(any(x.title_id == title_id for x in self.query.receivables(open_only=True)))

    def test_confirmacao_tipo_fluxo_caixa_e_falha_pos_commit(self):
        title_id = self._title("RECEBER", "100.00")
        command = SettleFinancialTitleCommand(title_id, Decimal("40.00"), "DINHEIRO", date.today())
        pending = self.actions.settle_receivable(command, context=self.context, confirmed=False)
        self.assertFalse(pending.executed)
        self.assertEqual(pending.sensitivity, ActionSensitivity.SENSITIVE)
        wrong = self.actions.settle_payable(command, context=self.context, confirmed=True)
        self.assertFalse(wrong.committed)

        paid = self.actions.settle_receivable(command, context=self.context, confirmed=True)
        payable_id = self._title("PAGAR", "30.00")
        self._settle("PAGAR", payable_id, "30.00")
        flow = self.query.cash_flow(date.today(), date.today())
        self.assertEqual({x.direction for x in flow}, {"ENTRADA", "SAIDA"})

        from commercial.application.financial_action_service import FinancialActionService
        service = FinancialActionService(self.actions._gateway, FailingFinancialEvents())
        post_commit = service.reverse_financial_payment(
            paid.payment_id, context=self.context, confirmed=True
        )
        self.assertTrue(post_commit.committed)
        self.assertTrue(post_commit.secondary_effect_failed)
        self.assertIn("não repita", post_commit.message)


if __name__ == "__main__":
    unittest.main()
