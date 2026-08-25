from __future__ import annotations

from decimal import Decimal
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_qt.commercial.nfe_purchase_import_dialog import NFePurchaseImportDialog


APP = QApplication.instance() or QApplication([])


def candidate(product_id=7):
    return SimpleNamespace(
        product_id=product_id, description="BRILHANTE 800G", criterion="EAN",
        similarity="100.00",
    )


def draft():
    return SimpleNamespace(
        draft_id="draft-1", number="123", supplier_name="Fornecedor",
        supplier_document="12345678000199", document_total="100.00",
        items=(SimpleNamespace(
            supplier_code="ABC", description="BRILHANTE CAIXA 20 UN",
            suggested_product_id=7, match_status="VINCULAR",
            candidates=(candidate(),),
        ),),
    )


class Application:
    def document(self, _draft_id):
        return SimpleNamespace(itens=(SimpleNamespace(
            codigo="ABC", descricao="BRILHANTE CAIXA 20 UN", cfop="5102",
            quantidade=Decimal("2"), unidade="CX", valor_unitario=Decimal("100"),
            codigo_barras="789", ncm="34025000", cest="",
        ),))

    def units(self): return (("CX", "Caixa"), ("UN", "Unidade"))
    def saved_link(self, _draft, _index):
        return {"produto_id": 7, "fator_conversao": "20", "unidade_estoque": "UN",
                "nome": "BRILHANTE", "codigo": "P7", "codigo_barras": "789"}


def test_grade_branca_compacta_recupera_vinculo_e_converte_caixa_para_unidade():
    dialog = NFePurchaseImportDialog(Application(), draft())
    assert "background:#ffffff" in dialog.table.styleSheet()
    assert dialog.table.rowHeight(0) <= 30
    assert "SALVO" in dialog.table.item(0, 0).text()
    assert dialog.table.item(0, 7).text() == "20"
    assert dialog.table.item(0, 8).text() == "UN"
    assert dialog.table.item(0, 9).text() == "40"
    assert dialog.table.item(0, 10).text() == "5"
    dialog.close()


def test_edicao_item_preco_em_margem_e_voltar_preservam_estado():
    dialog = NFePurchaseImportDialog(Application(), draft())
    dialog.factor.setText("10")
    assert dialog._save_selected() is True
    assert dialog._rows[0]["stock_quantity"] == Decimal("20.0000")
    dialog._show_prices()
    dialog.bulk_margin.setText("50")
    dialog._apply_bulk_margin()
    assert dialog._rows[0]["unit_cost"] == Decimal("10.00")
    assert dialog._rows[0]["preco"] == Decimal("15.00")
    dialog.pages.setCurrentIndex(0)
    assert dialog._rows[0]["fator"] == "10"
    dialog.close()
