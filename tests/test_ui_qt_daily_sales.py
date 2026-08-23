from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from commercial.application.query_dto import DailySaleSummary

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
    from ui_qt.commercial.daily_sales_dialog import DailySalesDialog
except (ImportError, OSError) as qt_error:
    QT_AVAILABLE = False
    QT_UNAVAILABLE_REASON = str(qt_error)
else:
    QT_AVAILABLE = True
    QT_UNAVAILABLE_REASON = ""


class _ViewModel:
    def __init__(self):
        self.sales = (DailySaleSummary(
            41, 7, "1x ITEM (R$ 10.00)", Decimal("10"),
            "2026-08-23 10:00:00", "PAGO", False,
        ),)
        self.previewed = []
        self.cancelled = []

    def list_daily_sales(self):
        return self.sales

    def list_budgets(self):
        return ()

    def daily_sale_preview_text(self, sale):
        self.previewed.append(sale.sale_id)
        return "COMPROVANTE"

    def print_daily_sale(self, sale):
        return "Impressora"

    def generate_daily_sale_pdf(self, sale):
        return "C:/teste.pdf"

    def cancel_daily_sale(self, sale_id, *, user="Sistema"):
        self.cancelled.append((sale_id, user))
        self.sales = ()


@unittest.skipUnless(QT_AVAILABLE, QT_UNAVAILABLE_REASON)
class DailySalesDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view_model = _ViewModel()
        self.dialog = DailySalesDialog(self.view_model)
        self.dialog.show()
        QApplication.processEvents()

    def tearDown(self):
        self.dialog.close()

    def test_lista_venda_e_enter_abre_uma_unica_previa(self):
        self.dialog.table.setFocus()
        with patch(
            "ui_qt.commercial.daily_sales_dialog.DailySalePreviewDialog.exec",
            return_value=QDialog.DialogCode.Rejected,
        ) as execute:
            QTest.keyClick(self.dialog.table, Qt.Key.Key_Return)
        execute.assert_called_once()
        self.assertEqual(self.view_model.previewed, [41])

    def test_shift_enter_volta_da_tabela_para_busca_sem_abrir(self):
        self.dialog.table.setFocus()
        with patch("ui_qt.commercial.daily_sales_dialog.DailySalePreviewDialog.exec") as execute:
            QTest.keyClick(
                self.dialog.table, Qt.Key.Key_Return,
                Qt.KeyboardModifier.ShiftModifier,
            )
        execute.assert_not_called()
        self.assertTrue(self.dialog.search.hasFocus())

    def test_auto_repeat_e_consumido_sem_abrir(self):
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier, "\r", True, 2,
        )
        with patch("ui_qt.commercial.daily_sales_dialog.DailySalePreviewDialog.exec") as execute:
            QApplication.sendEvent(self.dialog.table, event)
        execute.assert_not_called()

    def test_cancelamento_exige_confirmacao_e_executa_uma_vez(self):
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ):
            self.dialog._cancel()
        self.assertEqual(self.view_model.cancelled, [(41, "Sistema")])
        self.assertEqual(self.dialog.table.rowCount(), 0)

    def test_cancelamento_recusado_preserva_venda(self):
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No
        ):
            self.dialog._cancel()
        self.assertEqual(self.view_model.cancelled, [])
        self.assertEqual(self.dialog.table.rowCount(), 1)

    def test_documento_fiscal_nunca_chama_cancelamento_local(self):
        self.view_model.sales = (DailySaleSummary(
            42, 7, "ITEM", Decimal("10"), "2026-08-23", "PAGO", False,
            fiscal_status="AUTORIZADO",
        ),)
        self.dialog.reload()
        with patch.object(QMessageBox, "information") as information:
            self.dialog._cancel()
        information.assert_called_once()
        self.assertEqual(self.view_model.cancelled, [])

    def test_esc_fecha_apenas_dialogo(self):
        QTest.keyClick(self.dialog, Qt.Key.Key_Escape)
        self.assertFalse(self.dialog.isVisible())


if __name__ == "__main__":
    unittest.main()
