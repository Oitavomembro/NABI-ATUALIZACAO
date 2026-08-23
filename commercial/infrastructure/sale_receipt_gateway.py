from __future__ import annotations

from decimal import Decimal

from commercial.application.dto import CheckoutReceipt
from services.pdf_document_service import PDFDocumentService
from services.printing_service import PrintingService
from services.receipt_service import ReceiptService
from services.windows_file_opener import WindowsFileOpener


class NabiCodeSaleReceiptGateway:
    """Adapta o comprovante comercial confirmado aos serviços oficiais existentes."""

    def __init__(
        self,
        *,
        receipts: ReceiptService,
        printing: PrintingService,
        pdf: PDFDocumentService,
        opener: WindowsFileOpener | None = None,
        config_getter=lambda _key: "",
        item_allocator=None,
    ) -> None:
        self._receipts = receipts
        self._printing = printing
        self._pdf = pdf
        self._opener = opener or WindowsFileOpener()
        self._get_config = config_getter
        self._item_allocator = item_allocator

    def _items(self, receipt: CheckoutReceipt) -> list[dict]:
        items = [
            {
                "item": item.description,
                "qtd": item.quantity,
                "preco": item.net_unit_price,
                "subtotal": item.subtotal,
            }
            for item in receipt.items
        ]
        item_total = sum((Decimal(str(item["subtotal"])) for item in items), Decimal("0"))
        if item_total != receipt.total:
            if self._item_allocator is None:
                raise RuntimeError("O rateio comercial do comprovante não está configurado.")
            items = self._item_allocator(items, receipt.total)
        return items

    def print_thermal(self, receipt: CheckoutReceipt) -> str:
        items = self._items(receipt)
        text = self._receipts.build_sale_text(
            receipt.customer.customer_id, items, receipt.total, "VENDA",
            sale_id=receipt.sale_id,
        )
        printer = self._get_config("impressora_recibo") or "Padrão do Sistema"
        return self._printing.print_text(
            text,
            output_format=PrintingService.OFFICIAL_THERMAL_FORMAT,
            printer=printer,
            title="Comprovante de venda",
        )

    def generate_pdf(self, receipt: CheckoutReceipt) -> str:
        return self._pdf.generate_sale(
            receipt.customer.customer_id,
            self._items(receipt),
            receipt.total,
            "VENDA",
            document_id=receipt.sale_id,
        )

    def open_file(self, path: str) -> str:
        return self._opener.open(path)
