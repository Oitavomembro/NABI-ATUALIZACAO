from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import unittest

from commercial.application.dto import BudgetDocument, CheckoutCommand, CheckoutReceipt, CustomerRecord
from commercial.domain.cart import CartItem
from commercial.domain.credit import CreditTerms
from commercial.domain.payments import Payment, PaymentMethod, PaymentPlan
from commercial.infrastructure.checkout_gateway import NabiCodeCheckoutGateway
from commercial.infrastructure.customer_gateway import NabiCodeCustomerGateway
from commercial.infrastructure.product_gateway import NabiCodeProductGateway
from commercial.infrastructure.sale_receipt_gateway import NabiCodeSaleReceiptGateway
from commercial.infrastructure.budget_gateway import NabiCodeBudgetGateway
from commercial.infrastructure.suspended_sale_gateway import NabiCodeSuspendedSaleGateway


class FakeDatabase:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def fetch_one(self, sql, parameters):
        self.calls.append((sql, parameters))
        return self.row


class FakeCustomerRepository:
    def __init__(self):
        self.database = FakeDatabase((7, "C7", "CLIENTE", 70, 500, 100))

    def search_sales_suggestions(self, term, *, limit):
        return [SimpleNamespace(id=7, codigo="C7", nome="CLIENTE", numero_ficha=70)]


class FakeProductService:
    def listar(self, term):
        return [{
            "id": 10, "codigo": "P10", "codigo_barras": "789",
            "nome": "PRODUTO", "preco_venda": Decimal("25.00"), "ativo": 1,
        }]

    def buscar(self, product_id):
        return self.listar("")[0] if int(product_id) == 10 else None


class FakeLegacyPDVService:
    def __init__(self):
        self.rates = []

    def ratear_total_itens(self, items, total):
        self.rates.append((items, total))
        adjusted = [dict(item) for item in items]
        adjusted[0]["preco"] = total
        adjusted[0]["subtotal"] = total
        return adjusted


class FakeTransactionService:
    def __init__(self):
        self.kwargs = None

    def finalize_sale(self, **kwargs):
        self.kwargs = kwargs
        callback = kwargs.get("after_sale_in_transaction")
        if callback is not None:
            callback("CONNECTION", 44)
        total = sum(item["qtd"] * item["preco"] for item in kwargs["items"])
        return SimpleNamespace(
            sale_id=44,
            total=total,
            payment_description="PIX R$ 20.00 + CREDIARIO R$ 75.00",
            change=Decimal("0.00"),
            status="PENDENTE",
        )

    def cancel_sale(self, sale_id, *, user, before_cancel_commit=None):
        self.cancelled = (sale_id, user)
        if before_cancel_commit is not None:
            before_cancel_commit("CONNECTION", sale_id)


class FakeFiscalSaleService:
    def __init__(self):
        self.persisted = []
        self.released = []
        self.documents = []
        self.calls = []
        self.fiscal_service = SimpleNamespace(
            load_config=lambda: {"enabled": True, "default_model": "55"},
            release_number=lambda reservation_id, **_kwargs: self.released.append(reservation_id),
            reconcile_unknown=lambda queue_id: self.calls.append(("consult", queue_id)),
            retry_transmission=lambda queue_id: self.calls.append(("retry", queue_id)),
        )

    def recipient_for_customer(self, customer_id, *, model):
        assert customer_id == 7 and model == "55"
        return {"document": "12345678901", "name": "CLIENTE"}, 1

    def prepare(self, **_kwargs):
        return SimpleNamespace(
            reservation_id="R55", access_key="29" + "1" * 42,
            model="55", environment="HOMOLOGACAO",
        )

    def persist_draft(self, connection, sale_id, draft):
        self.persisted.append((connection, sale_id, draft.reservation_id))

    def list_sales(self):
        return list(self.documents)

    def enqueue_pending(self, *, sale_id):
        self.calls.append(("enqueue", sale_id))

    def cancel_authorized(self, **kwargs):
        self.calls.append(("cancel_sefaz", kwargs))

    def prepare_local_cancellation(self, connection, sale_id):
        self.calls.append(("prepare_local", connection, sale_id))

    def finalize_local_cancellation(self, *, sale_id):
        self.calls.append(("finalize_local", sale_id))


class FakeReceiptService:
    def __init__(self):
        self.calls = []

    def build_sale_text(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return "COMPROVANTE"

    def customer(self, customer_id):
        return SimpleNamespace(name="CONSUMIDOR FINAL" if customer_id == 1 else "CLIENTE")


class FakePrintingService:
    def __init__(self):
        self.calls = []

    def print_text(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return kwargs["printer"]


class FakePDFService:
    def __init__(self):
        self.calls = []

    def generate_sale(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return "C:/teste/venda.pdf"


class FakeOpener:
    def __init__(self):
        self.calls = []

    def open(self, path):
        self.calls.append(path)
        return path


class FakeBudgetPDVService:
    def __init__(self):
        self.documents = []

    def salvar_documento(
        self, tipo, items, *, cliente_id, cliente_nome, metadata=None,
    ):
        document = SimpleNamespace(
            id="B1", criada_em="2026-08-23T12:00:00", cliente_id=cliente_id,
            cliente_nome=cliente_nome, itens=tuple(items),
            total=sum(Decimal(str(item["qtd"])) * Decimal(str(item["preco"])) for item in items),
            tipo=tipo,
            metadata=dict(metadata or {}),
        )
        self.documents.append(document)
        return document

    def listar_documentos(self, tipo):
        return [item for item in self.documents if item.tipo == tipo]

    def consumir_documento(self, document_id):
        document = next(item for item in self.documents if item.id == document_id)
        self.documents.remove(document)
        return document


class FakeSuspendedPDVService:
    def __init__(self):
        self.open = []

    def suspender(self, items, *, cliente_id, cliente_nome):
        suspended = SimpleNamespace(
            id="S1", criada_em="2026-08-23T15:00:00",
            cliente_id=cliente_id, cliente_nome=cliente_nome,
            itens=tuple(items),
            total=sum(Decimal(str(item["qtd"])) * Decimal(str(item["preco"])) for item in items),
        )
        self.open.append(suspended)
        return suspended

    def listar_suspensas(self):
        return list(self.open)

    def reabrir(self, suspended_id):
        suspended = next(item for item in self.open if item.id == suspended_id)
        self.open.remove(suspended)
        return suspended


class NabiCodeGatewayTests(unittest.TestCase):
    def test_venda_suspensa_reutiliza_pdv_service_sem_checkout(self):
        pdv = FakeSuspendedPDVService()
        gateway = NabiCodeSuspendedSaleGateway(pdv)
        suspended = gateway.suspend(
            customer_id=7, customer_name="CLIENTE",
            items=(CartItem("PRODUTO", 2, "10", product_id=9, discount_percent="10"),),
        )
        self.assertEqual(suspended.customer_id, 7)
        self.assertEqual(suspended.items[0].product_id, 9)
        self.assertEqual(suspended.items[0].discount_percent, Decimal("10.00"))
        self.assertEqual(gateway.list_open()[0].suspended_id, "S1")
        self.assertEqual(gateway.resume("S1").suspended_id, "S1")
        self.assertEqual(gateway.list_open(), ())

    def test_texto_sem_id_nao_vira_cliente_ao_ler_suspensa_legacy(self):
        pdv = FakeSuspendedPDVService()
        stored = pdv.suspender(
            [{"item": "AVULSO", "qtd": 1, "preco": 5, "subtotal": 5,
              "item_avulso": True}],
            cliente_id=None, cliente_nome="TEXTO ANTIGO",
        )
        suspended = NabiCodeSuspendedSaleGateway(pdv).list_open()[0]
        self.assertEqual(stored.cliente_nome, "TEXTO ANTIGO")
        self.assertIsNone(suspended.customer_id)
        self.assertEqual(suspended.customer_name, "")

    def test_orcamento_reutiliza_servicos_legacy_sem_persistir_venda(self):
        pdv = FakeBudgetPDVService()
        receipts = FakeReceiptService()
        printing = FakePrintingService()
        pdf = FakePDFService()
        opener = FakeOpener()
        gateway = NabiCodeBudgetGateway(
            pdv=pdv, receipts=receipts, printing=printing, pdf=pdf,
            opener=opener, final_consumer_id=1,
            config_getter=lambda key: "IMPRESSORA" if key == "impressora_recibo" else "",
        )
        budget = gateway.save(
            customer_id=7, customer_name="CLIENTE",
            items=(CartItem("PRODUTO", 2, "10", product_id=9, discount_percent="10"),),
            payment_method="CREDIÁRIO", entry_amount="3.00", installments=3,
        )
        self.assertEqual(budget.total, Decimal("18.00"))
        self.assertEqual(budget.items[0].product_id, 9)
        self.assertEqual(budget.items[0].discount_percent, Decimal("10.00"))
        self.assertEqual(budget.payment_method, "CREDIÁRIO")
        self.assertEqual(budget.entry_amount, Decimal("3.00"))
        self.assertEqual(budget.installments, 3)
        preview = gateway.preview_text(budget)
        self.assertIn("COMPROVANTE", preview)
        self.assertIn("CONDIÇÃO ESTIMADA", preview)
        self.assertIn("NÃO É RECEBIMENTO", preview)
        self.assertIn("Saldo estimado: R$ 15,00 em 3x", preview)
        self.assertEqual(gateway.print_thermal(budget), "IMPRESSORA")
        self.assertEqual(gateway.generate_pdf(budget), "C:/teste/venda.pdf")
        gateway.open_file("C:/teste/venda.pdf")
        self.assertEqual(receipts.calls[0][0][3], "ORCAMENTO")
        self.assertEqual(pdf.calls[0][0][3], "ORCAMENTO")
        self.assertIsNone(pdf.calls[0][1]["document_id"])
        self.assertEqual(gateway.list_open()[0].budget_id, "B1")
        self.assertEqual(gateway.consume("B1").budget_id, "B1")
        self.assertEqual(gateway.list_open(), ())

    def test_saida_de_comprovante_reutiliza_servicos_oficiais_sem_persistir_venda(self):
        receipts = FakeReceiptService()
        printing = FakePrintingService()
        pdf = FakePDFService()
        opener = FakeOpener()
        gateway = NabiCodeSaleReceiptGateway(
            receipts=receipts,
            printing=printing,
            pdf=pdf,
            opener=opener,
            config_getter=lambda key: "IMPRESSORA RECIBO" if key == "impressora_recibo" else "",
            item_allocator=FakeLegacyPDVService().ratear_total_itens,
        )
        receipt = CheckoutReceipt(
            sale_id=44,
            customer=CustomerRecord(7, "C7", "CLIENTE"),
            items=(CartItem("ITEM", 2, Decimal("25.00")),),
            payments=(Payment(PaymentMethod.PIX, Decimal("50.00")),),
            total=Decimal("50.00"),
            financed_value=Decimal("0.00"),
            received=Decimal("50.00"),
            change=Decimal("0.00"),
            payment_description="PIX",
            status="PAGO",
        )

        self.assertEqual(gateway.print_thermal(receipt), "IMPRESSORA RECIBO")
        self.assertEqual(gateway.generate_pdf(receipt), "C:/teste/venda.pdf")
        self.assertEqual(gateway.open_file("C:/teste/venda.pdf"), "C:/teste/venda.pdf")
        self.assertEqual(receipts.calls[0][0][0], 7)
        self.assertEqual(receipts.calls[0][1]["sale_id"], 44)
        self.assertEqual(printing.calls[0][1]["printer"], "IMPRESSORA RECIBO")
        self.assertEqual(pdf.calls[0][1]["document_id"], 44)
        self.assertEqual(opener.calls, ["C:/teste/venda.pdf"])

    def test_comprovante_rateia_ajuste_pelo_mesmo_servico_comercial_do_checkout(self):
        receipts = FakeReceiptService()
        printing = FakePrintingService()
        pdf = FakePDFService()
        pdv = FakeLegacyPDVService()
        gateway = NabiCodeSaleReceiptGateway(
            receipts=receipts,
            printing=printing,
            pdf=pdf,
            opener=FakeOpener(),
            item_allocator=pdv.ratear_total_itens,
        )
        receipt = CheckoutReceipt(
            sale_id=45,
            customer=CustomerRecord(7, "C7", "CLIENTE"),
            items=(CartItem("ITEM", 1, Decimal("100.00")),),
            payments=(Payment(PaymentMethod.PIX, Decimal("90.00")),),
            total=Decimal("90.00"),
            financed_value=Decimal("0.00"),
            received=Decimal("90.00"),
            change=Decimal("0.00"),
            payment_description="PIX",
            status="PAGO",
        )

        gateway.print_thermal(receipt)

        self.assertEqual(pdv.rates[0][1], Decimal("90.00"))
        emitted_items = receipts.calls[0][0][1]
        self.assertEqual(emitted_items[0]["subtotal"], Decimal("90.00"))

    def test_checkout_gateway_preserva_autorizacao_pos(self):
        transaction = FakeTransactionService()
        gateway = NabiCodeCheckoutGateway(transaction, FakeLegacyPDVService())
        command = CheckoutCommand(
            customer_id=7,
            items=[CartItem("ITEM", 1, Decimal("100"))],
            payment_plan=PaymentPlan([
                Payment(PaymentMethod.CREDIT_CARD, Decimal("100"), "NSU123")
            ]),
        )
        gateway.checkout(command, customer=CustomerRecord(7, "C7", "CLIENTE"), user="op")
        payment = transaction.kwargs["payments"][0]
        self.assertEqual(payment["card_integration"], 2)
        self.assertEqual(payment["card_authorization"], "NSU123")

    def test_checkout_fiscal_persiste_nfe_na_mesma_transacao_da_venda(self):
        transaction = FakeTransactionService()
        fiscal = FakeFiscalSaleService()
        gateway = NabiCodeCheckoutGateway(transaction, FakeLegacyPDVService())
        gateway.bind_fiscal(fiscal, required=True)
        command = CheckoutCommand(
            customer_id=7,
            items=[CartItem("ITEM", 1, Decimal("10"), product_id=10)],
            payment_plan=PaymentPlan([Payment(PaymentMethod.PIX, Decimal("10"))]),
        )
        result = gateway.checkout(
            command, customer=CustomerRecord(7, "C7", "CLIENTE"), user="op"
        )
        self.assertEqual(result.sale_id, 44)
        self.assertEqual(fiscal.persisted, [("CONNECTION", 44, "R55")])
        self.assertEqual(gateway.last_fiscal_submission["status"], "ENFILEIRADO")

    def test_checkout_fiscal_nunca_aceita_item_avulso(self):
        gateway = NabiCodeCheckoutGateway(FakeTransactionService(), FakeLegacyPDVService())
        gateway.bind_fiscal(FakeFiscalSaleService(), required=True)
        command = CheckoutCommand(
            customer_id=7,
            items=[CartItem("AVULSO", 1, Decimal("10"))],
            payment_plan=PaymentPlan([Payment(PaymentMethod.PIX, Decimal("10"))]),
        )
        with self.assertRaisesRegex(ValueError, "itens estejam cadastrados"):
            gateway.checkout(
                command, customer=CustomerRecord(7, "C7", "CLIENTE"), user="op"
            )

    def test_resposta_desconhecida_agenda_consulta_e_nunca_reenvia(self):
        fiscal = FakeFiscalSaleService()
        fiscal.documents = [{
            "sale_id": 44, "status": "RESPOSTA_DESCONHECIDA", "queue_id": "Q44",
        }]
        gateway = NabiCodeCheckoutGateway(FakeTransactionService(), FakeLegacyPDVService())
        gateway.bind_fiscal(fiscal, required=True)

        message = gateway.recover_fiscal_sale(44)

        self.assertIn("Consulta oficial", message)
        self.assertEqual(fiscal.calls, [("consult", "Q44")])

    def test_falha_definitiva_permite_reenvio_controlado(self):
        fiscal = FakeFiscalSaleService()
        fiscal.documents = [{"sale_id": 44, "status": "FALHA", "queue_id": "Q44"}]
        gateway = NabiCodeCheckoutGateway(FakeTransactionService(), FakeLegacyPDVService())
        gateway.bind_fiscal(fiscal, required=True)

        message = gateway.recover_fiscal_sale(44)

        self.assertIn("Reenvio fiscal", message)
        self.assertEqual(fiscal.calls, [("retry", "Q44")])

    def test_estado_exibido_desconhecido_nunca_vira_reenvio_se_estado_mudar(self):
        fiscal = FakeFiscalSaleService()
        fiscal.documents = [{"sale_id": 44, "status": "FALHA", "queue_id": "Q44"}]
        gateway = NabiCodeCheckoutGateway(FakeTransactionService(), FakeLegacyPDVService())
        gateway.bind_fiscal(fiscal, required=True)

        with self.assertRaisesRegex(ValueError, "situação fiscal mudou"):
            gateway.recover_fiscal_sale(
                44, expected_status="RESPOSTA_DESCONHECIDA", allowed_action="CONSULTAR"
            )

        self.assertEqual(fiscal.calls, [])

    def test_resposta_desconhecida_recusa_acao_de_reenvio(self):
        fiscal = FakeFiscalSaleService()
        fiscal.documents = [{
            "sale_id": 44, "status": "RESPOSTA_DESCONHECIDA", "queue_id": "Q44",
        }]
        gateway = NabiCodeCheckoutGateway(FakeTransactionService(), FakeLegacyPDVService())
        gateway.bind_fiscal(fiscal, required=True)

        with self.assertRaisesRegex(ValueError, "somente consulta"):
            gateway.recover_fiscal_sale(
                44, expected_status="RESPOSTA_DESCONHECIDA", allowed_action="REENVIAR"
            )

        self.assertEqual(fiscal.calls, [])

    def test_cancelamento_fiscal_reverte_local_somente_depois_da_sefaz(self):
        transaction = FakeTransactionService()
        fiscal = FakeFiscalSaleService()
        gateway = NabiCodeCheckoutGateway(transaction, FakeLegacyPDVService())
        gateway.bind_fiscal(fiscal, required=True)

        gateway.cancel_fiscal_sale(
            44, password="segredo", justification="PROBLEMAS TÉCNICOS", user="operador"
        )

        self.assertEqual(fiscal.calls[0][0], "cancel_sefaz")
        self.assertEqual(fiscal.calls[1], ("prepare_local", "CONNECTION", 44))
        self.assertEqual(transaction.cancelled, (44, "operador"))
        self.assertEqual(fiscal.calls[2], ("finalize_local", 44))

    def test_customer_gateway_pesquisa_e_obtem_por_id(self):
        repository = FakeCustomerRepository()
        gateway = NabiCodeCustomerGateway(repository)
        self.assertEqual(gateway.search("cli")[0].customer_id, 7)
        customer = gateway.get(7)
        self.assertEqual(customer.customer_id, 7)
        self.assertEqual(customer.credit_limit, Decimal("500"))
        self.assertEqual(repository.database.calls[0][1], (7,))

    def test_product_gateway_reutiliza_service(self):
        gateway = NabiCodeProductGateway(FakeProductService())
        self.assertEqual(gateway.search("produto")[0].product_id, 10)
        self.assertEqual(gateway.get(10).unit_price, Decimal("25.00"))
        self.assertIsNone(gateway.get(99))

    def test_checkout_gateway_traduz_item_avulso_ajustes_e_crediario(self):
        transaction = FakeTransactionService()
        pdv = FakeLegacyPDVService()
        gateway = NabiCodeCheckoutGateway(transaction, pdv)
        plan = PaymentPlan([
            Payment(PaymentMethod.PIX, Decimal("20.00")),
            Payment(PaymentMethod.STORE_CREDIT, Decimal("75.00")),
        ])
        terms = CreditTerms.create(
            down_payment=Decimal("20.00"),
            financed_value=Decimal("75.00"),
            due_dates=[date(2026, 9, 22), date(2026, 10, 22)],
        )
        command = CheckoutCommand(
            customer_id=7,
            items=[CartItem("ITEM LIVRE", 1, Decimal("100.00"))],
            payment_plan=plan,
            credit_terms=terms,
            discount_amount=Decimal("5.00"),
        )
        result = gateway.checkout(
            command,
            customer=CustomerRecord(7, "C7", "CLIENTE"),
            user="operador",
        )

        self.assertEqual(result.sale_id, 44)
        self.assertEqual(transaction.kwargs["customer_id"], 7)
        self.assertEqual(transaction.kwargs["customer_name"], "CLIENTE")
        self.assertIsNone(transaction.kwargs["items"][0]["produto_id"])
        self.assertTrue(transaction.kwargs["items"][0]["item_avulso"])
        credit = transaction.kwargs["payments"][1]
        self.assertEqual(credit["parcelas"], 2)
        self.assertEqual(credit["primeiro_vencimento"], "2026-09-22")
        self.assertEqual(transaction.kwargs["received"], Decimal("95.00"))
        self.assertEqual(pdv.rates[0][1], Decimal("95.00"))


if __name__ == "__main__":
    unittest.main()
