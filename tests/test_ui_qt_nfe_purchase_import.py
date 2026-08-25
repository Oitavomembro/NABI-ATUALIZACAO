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

    def commit(self, _draft, rows, *, confirmed):
        assert confirmed is True
        return {
            "importacao_id": 55, "itens_criados": 0, "itens_vinculados": 1,
            "titulo_ids": [], "financeiro_indicacao": "Nenhum título criado.",
            "resultados": [{"descricao": rows[0]["descricao"], "status": "atualizado",
                            "quantidade_estoque": 40}],
        }


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
    dialog.back_to_items.click()
    assert dialog._rows[0]["fator"] == "10"
    dialog.close()


def test_vinculo_e_decisao_sao_automaticos_com_desvinculo_explicito():
    dialog = NFePurchaseImportDialog(Application(), draft())
    assert dialog._rows[0]["acao"] == "ATUALIZAR"
    assert dialog._rows[0]["produto_id"] == 7
    assert "ID 7" in dialog.linked_product.text()
    assert not hasattr(dialog, "action")
    assert not hasattr(dialog, "product")
    dialog.unlink.click()
    assert dialog._rows[0]["acao"] == "CRIAR"
    assert dialog._rows[0]["produto_id"] is None
    assert "produto novo" in dialog.linked_product.text()
    dialog.close()


def test_segunda_etapa_nao_expoe_quantidade_e_revisao_e_separada():
    dialog = NFePurchaseImportDialog(Application(), draft())
    dialog._show_prices()
    headers = [dialog.price_table.horizontalHeaderItem(i).text()
               for i in range(dialog.price_table.columnCount())]
    assert all("Qtd" not in header and "Quantidade" not in header for header in headers)
    dialog.review.click()
    assert dialog.pages.currentIndex() == 2
    assert "ATUALIZAR E VINCULAR" in dialog.confirmation_text.toPlainText()
    assert "Nenhuma comunicação com a SEFAZ" in dialog.confirmation_text.toPlainText()
    dialog.close()
