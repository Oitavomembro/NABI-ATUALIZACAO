from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from commercial.application.dto import ProductRecord

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog
    from tests.test_ui_qt_pdv import make_view_model
    from ui_qt.commercial.pdv_window import PDVWindow
    from ui_qt.commercial.product_search_dialog import ProductSearchDialog
except (ImportError, OSError) as qt_error:
    QT_AVAILABLE = False
    QT_UNAVAILABLE_REASON = str(qt_error)
else:
    QT_AVAILABLE = True
    QT_UNAVAILABLE_REASON = ""


PRODUCTS = (
    ProductRecord(9, "P9", "789", "CADEIRA CONFORTO", Decimal("149.90"), True, Decimal("8")),
    ProductRecord(10, "P10", "790", "MESA GRANDE", Decimal("399.00"), True, Decimal("2.5")),
)


def search_products(term: str, limit: int):
    normalized = str(term).strip().casefold()
    records = tuple(
        product for product in PRODUCTS
        if not normalized or normalized in " ".join(
            (product.code, product.barcode, product.description)
        ).casefold()
    )
    return records[:limit]


@unittest.skipUnless(QT_AVAILABLE, f"Runtime Qt indisponível: {QT_UNAVAILABLE_REASON}")
class ProductSearchDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = ProductSearchDialog(search_products)
        self.dialog.show()
        QApplication.processEvents()

    def tearDown(self):
        self.dialog.close()

    def test_exibe_nome_preco_e_estoque_em_area_ampliada(self):
        self.assertEqual(self.dialog.table.columnCount(), 3)
        self.assertEqual(
            [self.dialog.table.horizontalHeaderItem(index).text() for index in range(3)],
            ["NOME DO PRODUTO", "PREÇO", "ESTOQUE"],
        )
        self.assertEqual(self.dialog.table.item(0, 0).text(), "CADEIRA CONFORTO")
        self.assertEqual(self.dialog.table.item(0, 1).text(), "R$ 149,90")
        self.assertEqual(self.dialog.table.item(0, 2).text(), "8")
        self.assertGreaterEqual(self.dialog.minimumWidth(), 780)

    def test_enter_da_busca_move_uma_etapa_e_enter_da_lista_seleciona_id_real(self):
        self.assertTrue(self.dialog.search_input.hasFocus())
        QTest.keyClick(self.dialog.search_input, Qt.Key.Key_Return)
        self.assertTrue(self.dialog.table.hasFocus())
        self.assertIsNone(self.dialog.selected_product_id)
        QTest.keyClick(self.dialog.table, Qt.Key.Key_Return)
        self.assertEqual(self.dialog.selected_product_id, 9)
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)

    def test_shift_enter_volta_para_busca_sem_selecionar(self):
        self.dialog.table.setFocus()
        QTest.keyClick(
            self.dialog.table, Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
        )
        self.assertTrue(self.dialog.search_input.hasFocus())
        self.assertIsNone(self.dialog.selected_product_id)

    def test_auto_repeat_enter_e_consumido_sem_selecionar(self):
        self.dialog.table.setFocus()
        repeat = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier, "", True, 2,
        )
        QApplication.sendEvent(self.dialog.table, repeat)
        self.assertIsNone(self.dialog.selected_product_id)
        self.assertEqual(self.dialog.result(), 0)

    def test_esc_cancela_sem_identidade(self):
        QTest.keyClick(self.dialog, Qt.Key.Key_Escape)
        self.assertIsNone(self.dialog.selected_product_id)
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)


@unittest.skipUnless(QT_AVAILABLE, f"Runtime Qt indisponível: {QT_UNAVAILABLE_REASON}")
class ProductSearchPDVIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view_model, _gateway = make_view_model()
        self.window = PDVWindow(self.view_model)
        self.window.show()
        QApplication.processEvents()

    def tearDown(self):
        self.window.close()

    def test_pesquisa_ampliada_seleciona_product_id_e_retorna_a_quantidade(self):
        class AcceptedDialog:
            selected_product_id = 9

            def __init__(self, *_args, **_kwargs):
                pass

            @staticmethod
            def exec():
                return QDialog.DialogCode.Accepted

        with patch("ui_qt.commercial.pdv_window.ProductSearchDialog", AcceptedDialog):
            self.window._open_expanded_product_search()
        self.assertEqual(self.view_model.selected_product.product_id, 9)
        self.assertEqual(self.window.product_search.text(), "P9 — PRODUTO NOVE")
        self.assertTrue(self.window.quantity.hasFocus())

    def test_cancelar_pesquisa_preserva_estado_e_foca_busca_rapida(self):
        class RejectedDialog:
            selected_product_id = None

            def __init__(self, *_args, **_kwargs):
                pass

            @staticmethod
            def exec():
                return QDialog.DialogCode.Rejected

        with patch("ui_qt.commercial.pdv_window.ProductSearchDialog", RejectedDialog):
            self.window._open_expanded_product_search()
        self.assertIsNone(self.view_model.selected_product)
        self.assertTrue(self.window.product_search.hasFocus())

    def test_lista_rapida_continua_disponivel_pela_seta(self):
        self.window.product_search.setText("P9")
        self.window.product_results.hide()
        self.window._dropdown_button.click()
        self.assertTrue(self.window.product_results.isVisible())
        self.assertEqual(self.window.product_results.count(), 1)

    def test_modo_avulso_oculta_pesquisa_ampliada(self):
        self.window.loose_item.setChecked(True)
        self.assertFalse(self.window.expanded_product_search.isVisible())
        self.window._open_expanded_product_search()
        self.assertIsNone(self.view_model.selected_product)
