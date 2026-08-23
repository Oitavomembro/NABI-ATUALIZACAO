from __future__ import annotations

from services.pdf_document_service import PDFDocumentService
from services.printing_service import PrintingService
from services.receipt_service import ReceiptService


class FicharioCustomerReceiptOutput:
    """Comprovante oficial de recebimento, sem qualquer nova persistência financeira."""

    def __init__(self, database, pdf_dir, config_getter) -> None:
        self._get_config = config_getter
        self._receipts = ReceiptService(database, config_getter=config_getter)
        self._printing = PrintingService(config_getter)
        self._pdf = PDFDocumentService(
            connection_factory=database.connect,
            config_getter=config_getter,
            pdf_dir=pdf_dir,
        )

    def preview_text(self, movement_id: int, *, balance_before, balance_after) -> str:
        return self._receipts.build_payment_text(
            movement_id, (), balance_before=balance_before, balance_after=balance_after
        )

    def print_receipt(self, movement_id: int, *, balance_before, balance_after) -> str:
        text = self.preview_text(
            movement_id, balance_before=balance_before, balance_after=balance_after
        )
        output_format = self._printing.output_format("recibo")
        printer = self._get_config("impressora_recibo") or "Padrão do Sistema"
        return self._printing.print_text(
            text, output_format=output_format, printer=printer,
            title=f"Recibo de pagamento #{movement_id}",
        )

    def generate_pdf(
        self, movement_id: int, destination: str, *, balance_before, balance_after
    ) -> str:
        return self._pdf.generate_customer_payment(
            movement_id, (), destination,
            balance_before=balance_before, balance_after=balance_after,
        )
