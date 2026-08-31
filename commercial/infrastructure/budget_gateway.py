from __future__ import annotations

from decimal import Decimal

from commercial.application.dto import BudgetDocument
from commercial.domain.cart import CartItem
from commercial.domain.money import MoneyCodec
from services.pdf_document_service import PDFDocumentService
from services.pdv_service import PDVService
from services.printing_service import PrintingService
from services.receipt_service import ReceiptService
from services.windows_file_opener import WindowsFileOpener


class NabiCodeBudgetGateway:
    """Adapta orçamento Qt ao armazenamento e aos documentos oficiais do Legacy."""

    def __init__(
        self,
        *,
        pdv: PDVService,
        receipts: ReceiptService,
        printing: PrintingService,
        pdf: PDFDocumentService,
        final_consumer_id: int,
        opener: WindowsFileOpener | None = None,
        config_getter=lambda _key: "",
    ) -> None:
        self._pdv = pdv
        self._receipts = receipts
        self._printing = printing
        self._pdf = pdf
        self._final_consumer_id = int(final_consumer_id)
        self._opener = opener or WindowsFileOpener()
        self._get_config = config_getter

    @staticmethod
    def _stored_item(item: CartItem) -> dict:
        return {
            "produto_id": item.product_id,
            "item": item.description,
            "qtd": item.quantity,
            "preco_original": item.unit_price,
            "desconto_percentual": item.discount_percent,
            "preco": item.net_unit_price,
            "subtotal": item.subtotal,
            "item_avulso": item.is_loose,
        }

    @staticmethod
    def _cart_item(item: dict) -> CartItem:
        product_id = item.get("produto_id")
        return CartItem(
            description=str(item.get("item") or ""),
            quantity=Decimal(str(item.get("qtd", "0"))),
            unit_price=Decimal(str(item.get("preco_original", item.get("preco", "0")))),
            product_id=int(product_id) if product_id not in (None, "", 0, "0") else None,
            discount_percent=Decimal(str(item.get("desconto_percentual", "0"))),
        )

    def _document(self, stored) -> BudgetDocument:
        customer_id = stored.cliente_id or self._final_consumer_id
        customer = self._receipts.customer(customer_id)
        metadata = dict(getattr(stored, "metadata", None) or {})
        return BudgetDocument(
            budget_id=stored.id,
            created_at=stored.criada_em,
            customer_id=customer_id,
            customer_name=stored.cliente_nome or customer.name,
            items=tuple(self._cart_item(item) for item in stored.itens),
            total=stored.total,
            payment_method=metadata.get("payment_method", "A COMBINAR"),
            entry_amount=metadata.get("entry_amount", 0),
            installments=metadata.get("installments", 1),
            first_due_date=metadata.get("first_due_date"),
        )

    def save(
        self, *, customer_id: int, customer_name: str, items: tuple[CartItem, ...],
        payment_method: str = "A COMBINAR", entry_amount=0, installments: int = 1,
        first_due_date=None,
    ) -> BudgetDocument:
        proposal = BudgetDocument(
            budget_id="validation", created_at="validation", customer_id=customer_id,
            customer_name=customer_name, items=items,
            total=sum((item.subtotal for item in items), MoneyCodec.ZERO),
            payment_method=payment_method, entry_amount=entry_amount,
            installments=installments, first_due_date=first_due_date,
        )
        stored = self._pdv.salvar_documento(
            "ORCAMENTO",
            [self._stored_item(item) for item in items],
            cliente_id=customer_id,
            cliente_nome=customer_name,
            metadata={
                "payment_method": str(payment_method),
                "entry_amount": str(entry_amount),
                "installments": int(installments),
                "first_due_date": proposal.first_due_date.isoformat() if proposal.first_due_date else None,
            },
        )
        return self._document(stored)

    def list_open(self) -> tuple[BudgetDocument, ...]:
        return tuple(
            self._document(item) for item in self._pdv.listar_documentos("ORCAMENTO")
        )

    def consume(self, budget_id: str) -> BudgetDocument:
        stored = self._pdv.consumir_documento(str(budget_id))
        if stored.tipo != "ORCAMENTO":
            raise ValueError("O documento selecionado não é um orçamento.")
        return self._document(stored)

    def _receipt_items(self, budget: BudgetDocument) -> list[dict]:
        return [self._stored_item(item) for item in budget.items]

    def preview_text(self, budget: BudgetDocument) -> str:
        base = self._receipts.build_sale_text(
            budget.customer_id, self._receipt_items(budget), budget.total, "ORCAMENTO"
        )
        return f"{base.rstrip()}\n\n{self._terms_text(budget)}"

    @staticmethod
    def _terms_text(budget: BudgetDocument) -> str:
        financed = budget.total - budget.entry_amount
        text = (
            "CONDIÇÃO ESTIMADA (NÃO É RECEBIMENTO)\n"
            f"Forma: {budget.payment_method}\n"
            f"Entrada: R$ {MoneyCodec.format_br(budget.entry_amount)}\n"
            f"Saldo estimado: R$ {MoneyCodec.format_br(financed)} em "
            f"{budget.installments}x\n"
        )
        schedule = budget.estimated_schedule()
        if schedule:
            text += "VENCIMENTOS ESTIMADOS - NÃO SÃO COBRANÇAS\n"
            text += "\n".join(
                f"{item.number:02d}/{budget.installments:02d}  "
                f"{item.due_date:%d/%m/%Y}  R$ {MoneyCodec.format_br(item.amount)}"
                for item in schedule
            ) + "\n"
        elif financed > 0:
            text += "Vencimentos: a combinar\n"
        return text

    def print_thermal(self, budget: BudgetDocument) -> str:
        printer = self._get_config("impressora_recibo") or "Padrão do Sistema"
        return self._printing.print_text(
            self.preview_text(budget),
            output_format=PrintingService.OFFICIAL_THERMAL_FORMAT,
            printer=printer,
            title="Orçamento — sem valor fiscal",
        )

    def generate_pdf(self, budget: BudgetDocument) -> str:
        return self._pdf.generate_sale(
            budget.customer_id,
            self._receipt_items(budget),
            budget.total,
            "ORCAMENTO",
            document_id=None,
            budget_terms=self._terms_text(budget),
        )

    def open_file(self, path: str) -> str:
        return self._opener.open(path)
