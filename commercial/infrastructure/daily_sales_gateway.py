from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from commercial.application.query_dto import DailySaleSummary
from repositories.decimal_storage import DecimalStorage
from services.pdf_document_service import PDFDocumentService
from services.printing_service import PrintingService
from services.receipt_service import ReceiptService
from services.windows_file_opener import WindowsFileOpener


class NabiCodeDailySalesGateway:
    """Adapta o histórico comercial sem atravessar a fronteira Fiscal/SEFAZ."""

    _ITEM = re.compile(r"([\d.,]+)x\s+(.*?)\s+\(R\$\s*([\d.,]+)\)\s*$")

    def __init__(
        self,
        *,
        transaction_service,
        receipts: ReceiptService,
        printing: PrintingService,
        pdf: PDFDocumentService,
        opener: WindowsFileOpener | None = None,
        config_getter=lambda _key: "",
    ) -> None:
        self._transactions = transaction_service
        self._receipts = receipts
        self._printing = printing
        self._pdf = pdf
        self._opener = opener or WindowsFileOpener()
        self._get_config = config_getter

    def _summary(self, row: dict) -> DailySaleSummary:
        customer_id = row.get("cliente_id")
        customer_name = self._receipts.customer(customer_id).name
        return DailySaleSummary(
            sale_id=row["id"], customer_id=customer_id,
            description=str(row.get("descricao") or ""), total=row["valor"],
            occurred_at=str(row.get("data") or ""),
            status=str(row.get("status_pagamento") or ""),
            cancelled=str(row.get("status_pagamento") or "").upper() == "CANCELADO",
            fiscal_status=str(row.get("fiscal_status") or ""),
            fiscal_model=str(row.get("fiscal_model") or ""),
            access_key=str(row.get("access_key") or ""),
            protocol=str(row.get("protocol") or ""),
            fiscal_environment=str(row.get("fiscal_environment") or ""),
            fiscal_authorized_at=str(row.get("fiscal_authorized_at") or ""),
            customer_name=customer_name,
        )

    def list_today(self) -> tuple[DailySaleSummary, ...]:
        return tuple(self._summary(row) for row in self._transactions.list_sales_for_day())

    @classmethod
    def _items(cls, sale: DailySaleSummary) -> list[dict]:
        items: list[dict] = []
        for part in sale.description.split(" | "):
            match = cls._ITEM.match(part.strip())
            if not match:
                continue
            quantity = DecimalStorage.to_decimal(
                match.group(1).replace(",", "."), field="quantidade do item"
            )
            subtotal = DecimalStorage.to_decimal(
                match.group(3).replace(",", "."), field="subtotal do item"
            )
            if quantity <= 0:
                continue
            items.append({
                "qtd": quantity, "item": match.group(2).strip(),
                "preco": subtotal / quantity, "subtotal": subtotal,
            })
        if not items:
            items.append({
                "qtd": Decimal("1"), "item": sale.description or "Venda",
                "preco": sale.total, "subtotal": sale.total,
            })
        return items

    def preview_text(self, sale: DailySaleSummary) -> str:
        return self._receipts.build_sale_text(
            sale.customer_id, self._items(sale), sale.total, "VENDA", sale_id=sale.sale_id
        )

    def print_thermal(self, sale: DailySaleSummary) -> str:
        printer = self._get_config("impressora_recibo") or "Padrão do Sistema"
        return self._printing.print_text(
            self.preview_text(sale), output_format=PrintingService.OFFICIAL_THERMAL_FORMAT,
            printer=printer, title=f"Segunda via da venda #{sale.sale_id}",
        )

    def generate_pdf(self, sale: DailySaleSummary) -> str:
        return self._pdf.generate_sale(
            sale.customer_id, self._items(sale), sale.total, "VENDA",
            document_id=sale.sale_id,
        )

    def open_file(self, path: str) -> str:
        return self._opener.open(path)

    def cancel_local(self, sale_id: int, *, user: str) -> None:
        normalized_id = int(sale_id)
        sale = next((item for item in self.list_today() if item.sale_id == normalized_id), None)
        if sale is None:
            raise ValueError("Venda não encontrada nas vendas do dia.")
        if sale.cancelled:
            raise ValueError("A venda já está cancelada.")
        if sale.has_fiscal_document:
            raise ValueError(
                "Venda vinculada a documento fiscal. Use exclusivamente a Central Fiscal."
            )
        self._transactions.cancel_sale(normalized_id, user=str(user or "Sistema"))
