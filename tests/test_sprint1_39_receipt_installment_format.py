from __future__ import annotations

import unittest
from services.pdf_document_service import PDFDocumentService
from services.receipt_service import ReceiptService

class InstallmentFormatTests(unittest.TestCase):
    def test_dates_are_formatted_in_brazilian_format(self):
        self.assertEqual(PDFDocumentService._date_br("2026-09-05"), "05/09/2026")
        self.assertEqual(ReceiptService._date_br("2026-10-05"), "05/10/2026")

    def test_sale_receipts_do_not_repeat_pending_status(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        pdf = (root / "services/pdf_document_service.py").read_text(encoding="utf-8")
        receipt = (root / "services/receipt_service.py").read_text(encoding="utf-8")
        self.assertIn('f"{numero:02d}/{total_parcelas:02d}', pdf)
        self.assertIn('f"{int(numero):02d}/{total_parcelas:02d}', receipt)
        self.assertNotIn("| {parcela['status']", pdf)
        self.assertNotIn("| {st}", receipt)

if __name__ == "__main__":
    unittest.main()
