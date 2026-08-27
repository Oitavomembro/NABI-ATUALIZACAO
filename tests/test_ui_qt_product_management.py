from __future__ import annotations

import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from commercial.application.product_dto import ProductDetails
from ui_qt.commercial.product_management_dialog import (
    FiscalCatalogSearchDialog, ProductEditorDialog, ProductManagementDialog,
    StockMovementDialog,
)


PRODUCT = ProductDetails(
    17, "M17", "78917", "MESA LEGACY", Decimal("125.50"), Decimal("80"),
    Decimal("4"), Decimal("2"), False, "MERCADORIA", True,
)


class Application:
    def __init__(self):
        self.products = [PRODUCT]; self.created = []; self.updated = []
        self.received = []; self.removed = []; self.adjusted = []

    def search(self, term, *, limit=100):
        return tuple(self.products) if not term or term.casefold() in "mesa legacy m17 78917" else ()

    def get(self, product_id):
        if product_id != 17: raise ValueError("Produto não encontrado")
        return PRODUCT

    def create(self, command): self.created.append(command); return PRODUCT
    def update(self, command): self.updated.append(command); return PRODUCT
    def movements(self, product_id, *, limit=200): return ()
    def receive(self, command, *, confirmed):
        self.received.append((command, confirmed)); return SimpleNamespace(committed=True, message="ok")
    def remove(self, command, *, confirmed):
        self.removed.append((command, confirmed)); return SimpleNamespace(committed=True, message="ok")
    def adjust(self, command, *, confirmed):
        self.adjusted.append((command, confirmed)); return SimpleNamespace(committed=True, message="ok")
    def fiscal_issues(self, product_id):
        return (SimpleNamespace(message="ficha fiscal incompleta — CFOP, origem."),)
    def search_ncm(self, term, *, limit=50):
        return (SimpleNamespace(code="22021000", description="Águas, incluindo minerais"),)
    def search_cest(self, term, *, ncm="", limit=50):
        return (SimpleNamespace(code="0300700", description="Bebidas"),)


def _key(*, shift=False, repeat=False):
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        "", repeat, 1,
    )


def setup_module():
    global APP
    APP = QApplication.instance() or QApplication([])


def test_lista_prioriza_nome_preco_estoque_e_preserva_product_id():
    dialog = ProductManagementDialog(Application())
    assert dialog.table.horizontalHeaderItem(1).text() == "Nome / descrição"
    assert dialog.table.horizontalHeaderItem(2).text() == "Preço"
    assert dialog.table.horizontalHeaderItem(3).text() == "Estoque"
    assert dialog.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 17
    assert dialog.table.item(0, 1).text() == "MESA LEGACY"
    assert dialog.table.item(0, 2).text() == "R$ 125,50"
    assert dialog.table.item(0, 3).text() == "4"
    assert dialog.table.item(0, 1).font().bold()
    dialog.close()


def test_busca_por_codigo_barras_e_nome_atualiza_lista():
    dialog = ProductManagementDialog(Application())
    dialog.search.setText("78917"); dialog.reload(); assert dialog.table.rowCount() == 1
    dialog.search.setText("inexistente"); dialog.reload(); assert dialog.table.rowCount() == 0
    dialog.close()


def test_editor_novo_transporta_decimal_brasileiro_sem_float():
    application = Application(); editor = ProductEditorDialog(application)
    editor.description.setText("Cadeira")
    editor.sale_price.set_value(Decimal("10.25")); editor.cost_price.set_value(Decimal("5.10"))
    editor.current_stock.setText("2,5000"); editor.minimum_stock.setText("1,0000")
    editor._save()
    command = application.created[0]
    assert command.description == "Cadeira"
    assert command.sale_price == Decimal("10.25")
    assert command.current_stock == Decimal("2.5000")
    editor.close()


def test_edicao_nao_altera_saldo_diretamente_e_preserva_id_real():
    application = Application(); editor = ProductEditorDialog(application, PRODUCT)
    assert not editor.current_stock.isEnabled()
    editor.description.setText("Mesa nova"); editor._save()
    command = application.updated[0]
    assert command.product_id == 17
    assert command.current_stock == Decimal("4.0000")
    editor.close()


def test_editor_expoe_pendencia_e_transporta_ficha_fiscal_sem_inferir():
    application = Application(); editor = ProductEditorDialog(application, PRODUCT)
    assert "CFOP" in editor.fiscal_status.text()
    editor.ncm.setText("22021000"); editor.cest.setText("0300700"); editor.cfop.setText("5102")
    ProductEditorDialog._select_data(editor.origin, "0")
    ProductEditorDialog._select_data(editor.csosn, "102")
    ProductEditorDialog._select_data(editor.pis_cst, "49")
    ProductEditorDialog._select_data(editor.cofins_cst, "49")
    editor._save(); command = application.updated[0]
    assert (command.ncm, command.cest, command.cfop) == ("22021000", "0300700", "5102")
    assert command.fiscal_origin == "0" and command.fiscal_csosn == "102"
    assert command.fiscal_profile_source == "MANUAL"
    editor.close()


def test_catalogo_ncm_pesquisa_e_seleciona_codigo_real():
    dialog = FiscalCatalogSearchDialog(Application(), "NCM")
    dialog.query.setText("agua"); dialog._search()
    assert dialog.table.rowCount() == 1
    dialog._accept()
    assert dialog.selected_code == "22021000"
    dialog.close()


def test_enter_auto_repeat_nao_edita_nem_avanca():
    dialog = ProductManagementDialog(Application())
    with patch.object(dialog, "edit_product") as edit:
        assert dialog.eventFilter(dialog.table, _key(repeat=True)) is True
    edit.assert_not_called(); dialog.close()


def test_um_enter_na_tabela_abre_exatamente_uma_edicao():
    dialog = ProductManagementDialog(Application())
    with patch.object(dialog, "edit_product") as edit:
        assert dialog.eventFilter(dialog.table, _key()) is True
    edit.assert_called_once_with(); dialog.close()


def test_shift_enter_na_tabela_retorna_a_busca_sem_abrir():
    dialog = ProductManagementDialog(Application()); dialog.show(); dialog.table.setFocus(); APP.processEvents()
    with patch.object(dialog, "edit_product") as edit:
        assert dialog.eventFilter(dialog.table, _key(shift=True)) is True
        APP.processEvents()
    assert dialog.search.hasFocus(); edit.assert_not_called(); dialog.close()


def test_movimentacao_exige_revisao_e_executa_uma_unica_vez():
    application = Application(); dialog = StockMovementDialog(application, PRODUCT)
    dialog.amount.setText("3,5"); dialog.reason.setText("Inventário")
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog._confirm()
    assert len(application.received) == 1
    command, confirmed = application.received[0]
    assert command.product_id == 17 and command.amount == Decimal("3.5000")
    assert confirmed is True
    dialog.close()


def test_cancelar_revisao_nao_movimenta_e_mantem_foco_operacional():
    application = Application(); dialog = StockMovementDialog(application, PRODUCT)
    dialog.amount.setText("1"); dialog.reason.setText("Teste")
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        dialog._confirm()
    assert application.received == []
    assert dialog.result() == 0
    dialog.close()


def test_auto_repeat_no_botao_de_movimento_nao_confirma():
    application = Application(); dialog = StockMovementDialog(application, PRODUCT)
    dialog.amount.setText("1"); dialog.reason.setText("Teste")
    assert dialog.eventFilter(dialog.confirm, _key(repeat=True)) is True
    assert application.received == []
    dialog.close()
