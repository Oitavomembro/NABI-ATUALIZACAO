from __future__ import annotations

import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from commercial.application.query_dto import DailySaleSummary

try:
    from PySide6.QtCore import QDate, QEvent, Qt
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
        self.requested_days = []

    def list_daily_sales(self, day=None):
        self.requested_days.append(day)
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

    def cancel_daily_sale(self, sale_id, *, user="Sistema", day=None):
        self.cancelled.append((sale_id, user, day))
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
        self.assertEqual(
            self.view_model.cancelled,
            [(41, "Sistema", self.dialog.selected_day)],
        )
        self.assertEqual(self.dialog.table.rowCount(), 0)

    def test_cancelamento_recusado_preserva_venda(self):
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No
        ):
            self.dialog._cancel()
        self.assertEqual(self.view_model.cancelled, [])
        self.assertEqual(self.dialog.table.rowCount(), 1)

    def test_resposta_desconhecida_nunca_cancela_nem_reenvia(self):
        self.view_model.sales = (DailySaleSummary(
            42, 7, "ITEM", Decimal("10"), "2026-08-23", "PAGO", False,
            fiscal_status="RESPOSTA_DESCONHECIDA",
        ),)
        self.dialog.reload()
        with patch.object(QMessageBox, "warning") as warning:
            self.dialog._cancel()
        warning.assert_called_once()
        self.assertEqual(self.view_model.cancelled, [])

    def test_motivo_fiscal_padrao_e_problemas_tecnicos(self):
        self.assertEqual(self.dialog.DEFAULT_CANCELLATION_REASON, "PROBLEMAS TÉCNICOS")

    def test_seletor_consulta_data_antiga_sem_limite_de_historico_recente(self):
        selected = date(2019, 3, 14)
        self.dialog.date_selector.setDate(QDate(2019, 3, 14))
        QApplication.processEvents()
        self.assertEqual(self.dialog.selected_day, selected)
        self.assertEqual(self.view_model.requested_days[-1], selected)
        self.assertIn("14/03/2019", self.dialog.title.text())

    def test_botoes_navegam_e_hoje_retorna_para_data_atual(self):
        original = self.dialog.selected_day
        self.dialog.previous_day_button.click()
        self.assertEqual(self.dialog.selected_day, original - timedelta(days=1))
        self.dialog.today_button.click()
        self.assertEqual(self.dialog.selected_day, date.today())
        self.assertFalse(self.dialog.next_day_button.isEnabled())

    def test_acao_fiscal_muda_de_consulta_para_reenvio_somente_em_falha(self):
        self.view_model.sales = (DailySaleSummary(
            42, 7, "ITEM", Decimal("10"), "2026-08-23", "PAGO", False,
            fiscal_status="RESPOSTA_DESCONHECIDA",
        ),)
        self.dialog.reload()
        self.assertEqual(self.dialog.recover_button.text(), "Consultar situação na SEFAZ")
        self.assertTrue(self.dialog.recover_button.isVisible())
        self.assertFalse(self.dialog.retry_button.isVisible())
        self.view_model.sales = (DailySaleSummary(
            42, 7, "ITEM", Decimal("10"), "2026-08-23", "PAGO", False,
            fiscal_status="FALHA",
        ),)
        self.dialog.reload()
        self.assertFalse(self.dialog.recover_button.isVisible())
        self.assertTrue(self.dialog.retry_button.isVisible())
        self.assertEqual(self.dialog.retry_button.text(), "Reenviar NF-e")

    def test_denegacao_ou_codigo_desconhecido_nunca_oferece_reenvio(self):
        for error in (
            "301: Uso denegado: irregularidade fiscal do emitente",
            "999: Retorno novo sem política aprovada",
        ):
            self.view_model.sales = (DailySaleSummary(
                42, 7, "ITEM", Decimal("10"), "2026-08-23", "PAGO", False,
                fiscal_status="FALHA", fiscal_last_error=error,
            ),)
            self.dialog.reload()
            self.assertFalse(self.dialog.retry_button.isVisible())

    def test_719_exibe_motivo_e_permite_correcao_controlada(self):
        self.view_model.sales = (DailySaleSummary(
            42, 7, "ITEM", Decimal("10"), "2026-08-23", "PAGO", False,
            fiscal_status="FALHA",
            fiscal_last_error="719: NF-e sem identificação do destinatário",
        ),)
        self.dialog.reload()
        self.assertIn("719", self.dialog.table.item(0, 6).text())
        self.assertTrue(self.dialog.retry_button.isVisible())

    def test_acompanhamento_sefaz_mostra_progresso_e_compara_retorno(self):
        failed = DailySaleSummary(
            42, 7, "ITEM", Decimal("10"), "2026-08-23", "PAGO", False,
            fiscal_status="FALHA", fiscal_last_error="486: Grupo autXML ausente",
        )
        self.view_model.sales = (failed,)
        self.dialog.reload()
        self.dialog._begin_fiscal_wait(failed, "Reenvio fiscal agendado.")
        self.assertTrue(self.dialog.fiscal_progress.isVisible())
        self.assertFalse(self.dialog.retry_button.isEnabled())
        self.view_model.sales = (DailySaleSummary(
            42, 7, "ITEM", Decimal("10"), "2026-08-23", "PAGO", False,
            fiscal_status="FALHA", fiscal_last_error="100: Autorizado para teste",
        ),)
        with patch.object(QMessageBox, "information") as information:
            self.dialog._poll_fiscal_result()
        self.assertFalse(self.dialog.fiscal_progress.isVisible())
        self.assertIn("mudou", information.call_args.args[2])

    def test_modo_fiscal_destaca_registro_antigo_sem_vinculo(self):
        dialog = DailySalesDialog(self.view_model, fiscal_mode=True)
        try:
            self.assertEqual(dialog.table.item(0, 6).text(), "ERRO — SEM VÍNCULO FISCAL")
        finally:
            dialog.close()

    def test_esc_fecha_apenas_dialogo(self):
        QTest.keyClick(self.dialog, Qt.Key.Key_Escape)
        self.assertFalse(self.dialog.isVisible())


if __name__ == "__main__":
    unittest.main()
