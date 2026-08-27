from __future__ import annotations

from decimal import Decimal
from copy import deepcopy
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

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
    assert dialog.table.horizontalHeaderItem(0).text() == "Código"
    assert dialog.table.horizontalHeaderItem(1).text() == "Nome do produto"
    assert dialog.table.horizontalHeaderItem(9).text() == "Vínculo"
    assert dialog.table.horizontalHeader().sectionsMovable() is True
    assert dialog.table.columnWidth(1) <= 420
    assert dialog.table.columnWidth(0) <= 120
    assert "SALVO" in dialog.table.item(0, 9).text()
    assert dialog.table.item(0, 5).text() == "20"
    assert dialog.table.item(0, 6).text() == "UN"
    assert dialog.table.item(0, 7).text() == "40"
    assert dialog.table.item(0, 8).text() == "5"
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


def test_troca_de_linha_atualiza_painel_sem_reconstruir_tabela():
    second = SimpleNamespace(
        supplier_code="XYZ", description="SEGUNDO PRODUTO CAIXA 6 UN",
        suggested_product_id=None, match_status="NOVO", candidates=(),
    )
    two_items = draft()
    two_items.items = two_items.items + (second,)

    class TwoItemsApplication(Application):
        def document(self, _draft_id):
            first = super().document(_draft_id).itens[0]
            return SimpleNamespace(itens=(first, SimpleNamespace(
                codigo="XYZ", descricao=second.description, cfop="5102",
                quantidade=Decimal("3"), unidade="CX", valor_unitario=Decimal("60"),
                codigo_barras="790", ncm="34025000", cest="",
            )))

        def saved_link(self, _draft, index):
            return super().saved_link(_draft, index) if index == 0 else None

    dialog = NFePurchaseImportDialog(TwoItemsApplication(), two_items)
    dialog._render_rows = Mock()
    dialog.table.selectRow(1); APP.processEvents()
    assert dialog.name.text() == "SEGUNDO PRODUTO CAIXA 6 UN"
    assert "produto novo" in dialog.linked_product.text()
    dialog._render_rows.assert_not_called()
    dialog.close()


def test_troca_de_linha_nao_copia_edicao_para_o_produto_seguinte():
    second = SimpleNamespace(
        supplier_code="XYZ", description="SEGUNDO PRODUTO",
        suggested_product_id=None, match_status="NOVO", candidates=(),
    )
    two_items = draft(); two_items.items = two_items.items + (second,)

    class TwoItemsApplication(Application):
        def document(self, _draft_id):
            first = super().document(_draft_id).itens[0]
            return SimpleNamespace(itens=(first, SimpleNamespace(
                codigo="XYZ", descricao="SEGUNDO PRODUTO", cfop="5102",
                quantidade=Decimal("3"), unidade="UN", valor_unitario=Decimal("2"),
                codigo_barras="790", ncm="19059090", cest="",
            )))
        def saved_link(self, _draft, index):
            return super().saved_link(_draft, index) if index == 0 else None
        def save_draft(self, *_args, **_kwargs): return 1

    dialog = NFePurchaseImportDialog(TwoItemsApplication(), two_items)
    dialog.name.setText("PRIMEIRO EDITADO"); dialog.barcode.setText("111")
    dialog.factor.setText("6")
    dialog.table.selectRow(1); APP.processEvents()
    assert dialog._rows[0]["descricao"] == "PRIMEIRO EDITADO"
    assert dialog._rows[0]["codigo_barras"] == "111"
    assert dialog._rows[1]["descricao"] == "SEGUNDO PRODUTO"
    assert dialog._rows[1]["codigo_barras"] == "790"
    assert dialog._rows[1]["fator"] == "1"
    assert dialog.name.text() == "SEGUNDO PRODUTO"
    assert dialog.barcode.text() == "790"
    dialog.close()


def test_clique_em_salvar_na_segunda_linha_nao_grava_no_primeiro_produto():
    second = SimpleNamespace(
        supplier_code="ZERO", description="REFRIG IT GUAR ZERO ACUCAR PET 2L",
        suggested_product_id=None, match_status="NOVO", candidates=(),
    )
    two_items = draft(); two_items.items = two_items.items + (second,)

    class TwoItemsApplication(Application):
        def document(self, _draft_id):
            first = super().document(_draft_id).itens[0]
            return SimpleNamespace(itens=(first, SimpleNamespace(
                codigo="ZERO", descricao=second.description, cfop="5405",
                quantidade=Decimal("2"), unidade="PAC", valor_unitario=Decimal("35.39"),
                codigo_barras="790", ncm="22021000", cest="",
            )))
        def saved_link(self, _draft, index):
            return super().saved_link(_draft, index) if index == 0 else None
        def save_draft(self, *_args, **_kwargs): return 1

    dialog = NFePurchaseImportDialog(TwoItemsApplication(), two_items)
    original_first = deepcopy(dialog._rows[0])
    dialog.table.selectRow(1); APP.processEvents()
    dialog.name.setText("REFRIGERANTE ZERO ACUCAR EDITADO")
    dialog.barcode.setText("2222222222222")
    dialog.factor.setText("12")
    dialog.save_item.click(); APP.processEvents()

    assert dialog._rows[0]["descricao"] == original_first["descricao"]
    assert dialog._rows[0]["codigo_barras"] == original_first["codigo_barras"]
    assert dialog._rows[0]["fator"] == original_first["fator"]
    assert dialog._rows[1]["descricao"] == "REFRIGERANTE ZERO ACUCAR EDITADO"
    assert dialog._rows[1]["codigo_barras"] == "2222222222222"
    assert dialog._rows[1]["fator"] == "12"
    dialog.close()


def test_sete_itens_parecidos_mantem_edicao_isolada_em_trocas_rapidas():
    names = (
        "REFRIG IT GUAR Z AC PET 2L",
        "REFRIG IT GUAR PET 2L",
        "REFRIG IT LIM PET 2L",
        "REFRIG IT LAR PET 2L",
        "REFRIG IT COLA PET 2L",
        "REFRIG IT COLA ZERO PET 2L",
        "ENERG TNT ORIG LT 473ML PACK 6",
    )
    many = draft()
    many.items = tuple(SimpleNamespace(
        supplier_code=f"200{i:03d}CR4", description=name,
        suggested_product_id=None, match_status="NOVO", candidates=(),
    ) for i, name in enumerate(names, start=1))

    class ManyItemsApplication(Application):
        def document(self, _draft_id):
            return SimpleNamespace(itens=tuple(SimpleNamespace(
                codigo=f"200{i:03d}CR4", descricao=name,
                cfop="5910" if i in (1, 6) else "5405",
                quantidade=Decimal(str((i % 3) + 1)), unidade="PAC",
                valor_unitario=Decimal(str(30 + i)),
                codigo_barras=f"7897305009{i:03d}", ncm="22021000", cest="",
            ) for i, name in enumerate(names, start=1)))

        def saved_link(self, _draft, _index): return None
        def save_draft(self, *_args, **_kwargs): return 1

    dialog = NFePurchaseImportDialog(ManyItemsApplication(), many)
    expected = []
    for index, original_name in enumerate(names):
        dialog.table.selectRow(index); APP.processEvents()
        edited_name = f"{original_name} EDITADO {index + 1}"
        barcode = f"7890000000{index + 1:03d}"
        factor = str(index + 2)
        dialog.name.setText(edited_name)
        dialog.barcode.setText(barcode)
        dialog.factor.setText(factor)
        expected.append((edited_name, barcode, factor))

    for index in reversed(range(len(names))):
        dialog.table.selectRow(index); APP.processEvents()
        assert dialog.name.text() == expected[index][0]
        assert dialog.barcode.text() == expected[index][1]
        assert dialog.factor.text() == expected[index][2]
        assert dialog._rows[index]["descricao"] == expected[index][0]
        assert dialog._rows[index]["codigo_barras"] == expected[index][1]
        assert dialog._rows[index]["fator"] == expected[index][2]
    dialog.close()


def test_troca_por_teclado_preserva_normal_e_zero_acucar_independentes():
    second = SimpleNamespace(
        supplier_code="ZERO", description="REFRIG IT GUAR ZERO ACUCAR PET 2L",
        suggested_product_id=None, match_status="NOVO", candidates=(),
    )
    two_items = draft(); two_items.items = two_items.items + (second,)

    class KeyboardApplication(Application):
        def document(self, _draft_id):
            first = SimpleNamespace(
                codigo="NORMAL", descricao="REFRIG IT GUAR PET 2L", cfop="5405",
                quantidade=Decimal("2"), unidade="PAC", valor_unitario=Decimal("35.50"),
                codigo_barras="7891111111111", ncm="22021000", cest="",
            )
            zero = SimpleNamespace(
                codigo="ZERO", descricao=second.description, cfop="5405",
                quantidade=Decimal("2"), unidade="PAC", valor_unitario=Decimal("35.39"),
                codigo_barras="7892222222222", ncm="22021000", cest="",
            )
            return SimpleNamespace(itens=(first, zero))

        def saved_link(self, _draft, _index): return None
        def save_draft(self, *_args, **_kwargs): return 1

    dialog = NFePurchaseImportDialog(KeyboardApplication(), two_items)
    dialog.table.setFocus()
    dialog.name.setText("REFRIGERANTE NORMAL")
    dialog.barcode.setText("1111111111111")
    dialog.factor.setText("6")
    QTest.keyClick(dialog.table, Qt.Key.Key_Down); APP.processEvents()
    assert dialog.name.text() == "REFRIG IT GUAR ZERO ACUCAR PET 2L"
    dialog.name.setText("REFRIGERANTE ZERO ACUCAR")
    dialog.barcode.setText("2222222222222")
    dialog.factor.setText("12")
    QTest.keyClick(dialog.table, Qt.Key.Key_Up); APP.processEvents()
    assert dialog.name.text() == "REFRIGERANTE NORMAL"
    assert dialog.barcode.text() == "1111111111111"
    assert dialog.factor.text() == "6"
    QTest.keyClick(dialog.table, Qt.Key.Key_Down); APP.processEvents()
    assert dialog.name.text() == "REFRIGERANTE ZERO ACUCAR"
    assert dialog.barcode.text() == "2222222222222"
    assert dialog.factor.text() == "12"
    dialog.close()


def test_fator_invalido_impede_troca_e_nao_contamina_linha_destino(monkeypatch):
    second = SimpleNamespace(
        supplier_code="B", description="PRODUTO B",
        suggested_product_id=None, match_status="NOVO", candidates=(),
    )
    two_items = draft(); two_items.items = two_items.items + (second,)

    class TwoItemsApplication(Application):
        def document(self, _draft_id):
            first = super().document(_draft_id).itens[0]
            return SimpleNamespace(itens=(first, SimpleNamespace(
                codigo="B", descricao="PRODUTO B", cfop="5102",
                quantidade=Decimal("1"), unidade="UN", valor_unitario=Decimal("5"),
                codigo_barras="222", ncm="", cest="",
            )))
        def saved_link(self, _draft, index): return super().saved_link(_draft, index) if index == 0 else None
        def save_draft(self, *_args, **_kwargs): return 1

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    dialog = NFePurchaseImportDialog(TwoItemsApplication(), two_items)
    dialog.name.setText("PRIMEIRO EM CORRECAO")
    dialog.factor.setText("0")
    dialog.table.selectRow(1); APP.processEvents()
    assert dialog.table.currentRow() == 0
    assert dialog._editor_row == 0
    assert dialog.name.text() == "PRIMEIRO EM CORRECAO"
    assert dialog._rows[1]["descricao"] == "PRODUTO B"
    assert warnings and "Corrija o item atual" in warnings[-1]
    dialog.close()


def test_rascunho_restaurado_preserva_cada_linha_sem_misturar_estado():
    second = SimpleNamespace(
        supplier_code="ZERO", description="REFRIG ZERO ACUCAR",
        suggested_product_id=None, match_status="NOVO", candidates=(),
    )
    two_items = draft(); two_items.items = two_items.items + (second,)

    class DurableApplication(Application):
        def __init__(self): self.last_state = None
        def document(self, _draft_id):
            first = super().document(_draft_id).itens[0]
            return SimpleNamespace(itens=(first, SimpleNamespace(
                codigo="ZERO", descricao=second.description, cfop="5405",
                quantidade=Decimal("2"), unidade="PAC", valor_unitario=Decimal("20"),
                codigo_barras="222", ncm="22021000", cest="",
            )))
        def saved_link(self, _draft, index): return super().saved_link(_draft, index) if index == 0 else None
        def save_draft(self, _draft, rows, *, page=0):
            self.last_state = {"version": 1, "page": page, "rows": deepcopy(list(rows))}
            return 1

    application = DurableApplication()
    first_dialog = NFePurchaseImportDialog(application, two_items)
    first_dialog.name.setText("NORMAL EDITADO"); first_dialog.factor.setText("6")
    first_dialog.table.selectRow(1); APP.processEvents()
    first_dialog.name.setText("ZERO EDITADO"); first_dialog.factor.setText("12")
    first_dialog._checkpoint()
    restored_state = deepcopy(application.last_state)
    first_dialog.close()

    restored = NFePurchaseImportDialog(application, two_items, restored_state=restored_state)
    restored.table.selectRow(0); APP.processEvents()
    assert (restored.name.text(), restored.factor.text()) == ("NORMAL EDITADO", "6")
    restored.table.selectRow(1); APP.processEvents()
    assert (restored.name.text(), restored.factor.text()) == ("ZERO EDITADO", "12")
    restored.close()


def test_codigo_de_barras_repetido_bloqueia_antes_do_commit(monkeypatch):
    second = SimpleNamespace(
        supplier_code="XYZ", description="SEGUNDO PRODUTO",
        suggested_product_id=None, match_status="NOVO", candidates=(),
    )
    two_items = draft(); two_items.items = two_items.items + (second,)

    class DuplicateApplication(Application):
        def __init__(self): self.commit_calls = 0
        def document(self, _draft_id):
            first = super().document(_draft_id).itens[0]
            return SimpleNamespace(itens=(first, SimpleNamespace(
                codigo="XYZ", descricao="SEGUNDO PRODUTO", cfop="5102",
                quantidade=Decimal("1"), unidade="UN", valor_unitario=Decimal("2"),
                codigo_barras="789", ncm="19059090", cest="",
            )))
        def saved_link(self, _draft, index): return None
        def commit(self, *_args, **_kwargs): self.commit_calls += 1

    application = DuplicateApplication()
    dialog = NFePurchaseImportDialog(application, two_items)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    dialog._commit()
    assert application.commit_calls == 0
    assert warnings and "789" in warnings[-1] and "linhas 1, 2" in warnings[-1]
    assert dialog.pages.currentIndex() == 0
    dialog.close()


def test_tabela_de_precos_forca_texto_escuro_em_todas_as_linhas():
    dialog = NFePurchaseImportDialog(Application(), draft())
    dialog._show_prices()
    for column in (0, 1, 2, 5):
        assert dialog.price_table.item(0, column).foreground().color().name() in {
            "#111827", "#991b1b"
        }
    assert "QTableWidget QLineEdit" in dialog.price_table.styleSheet()
    dialog.close()


def test_desfazer_desvinculo_restaura_exatamente_o_vinculo_anterior():
    dialog = NFePurchaseImportDialog(Application(), draft())
    original = dict(dialog._rows[0])
    dialog._unlink_selected()
    assert dialog._rows[0]["produto_id"] is None
    assert dialog.restore_link.isEnabled()
    dialog._restore_selected_link()
    assert dialog._rows[0]["produto_id"] == original["produto_id"]
    assert dialog._rows[0]["acao"] == original["acao"]
    assert dialog._rows[0]["status"] == original["status"]
    assert dialog._rows[0]["saved"] == original["saved"]
    assert not dialog.restore_link.isEnabled()
    dialog.close()


def test_fontes_modos_e_colunas_da_tabela_de_precos_sao_ajustaveis():
    dialog = NFePurchaseImportDialog(Application(), draft())
    assert [dialog.review_view_mode.itemText(i) for i in range(dialog.review_view_mode.count())] == ["Detalhes", "Compacto"]
    assert [dialog.price_view_mode.itemText(i) for i in range(dialog.price_view_mode.count())] == ["Detalhes", "Compacto"]
    dialog.review_font_size.setCurrentIndex(dialog.review_font_size.findData(16))
    dialog.price_font_size.setCurrentIndex(dialog.price_font_size.findData(18))
    assert "font-size:16px" in dialog.table.styleSheet()
    assert "font-size:18px" in dialog.price_table.styleSheet()
    dialog._show_prices()
    assert dialog.price_table.horizontalHeader().sectionsMovable() is True
    assert all(dialog.price_table.columnWidth(i) <= cap for i, cap in enumerate((75, 460, 125, 105, 135, 260)))
    dialog.close()


def test_confirmacao_exibe_tabela_branca_organizada_e_resumos():
    dialog = NFePurchaseImportDialog(Application(), draft())
    dialog._show_prices(); dialog._show_confirmation()
    headers = [dialog.confirmation_table.horizontalHeaderItem(i).text() for i in range(8)]
    assert headers == ["Produto", "Ação", "Fator", "Conversão", "Unidade", "Custo", "Margem", "Preço"]
    assert "background:#ffffff" in dialog.confirmation_table.styleSheet()
    assert dialog.confirmation_table.horizontalHeader().sectionsMovable() is True
    assert "Fornecedor: Fornecedor" in dialog.confirmation_supplier.text()
    assert "Nenhuma comunicação com a SEFAZ" in dialog.confirmation_notes.text()
    dialog.close()


def test_nabi_sugere_fator_explicito_mas_so_aplica_apos_confirmacao(monkeypatch):
    dialog = NFePurchaseImportDialog(Application(), draft())
    dialog.name.setText("PRODUTO CAIXA COM 12 UN")
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    dialog.suggest_factor.click()
    assert dialog.factor_kind.currentData() == "MULTIPLICAR"
    assert dialog.factor.text() == "12"
    assert "24 UN" in dialog.conversion.text()
    dialog.close()


def test_nabi_nao_inventa_fator_sem_evidencia(monkeypatch):
    dialog = NFePurchaseImportDialog(Application(), draft())
    dialog.name.setText("PRODUTO SEM QUANTIDADE DECLARADA")
    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: shown.append(args[2]))
    dialog.suggest_factor.click()
    assert dialog.factor.text() == "20"
    assert shown and "não encontrei" in shown[0].lower()
    dialog.close()


def test_autosave_exibe_sucesso_sem_alegar_gravacao_operacional():
    class DurableApplication(Application):
        def save_draft(self, _draft, _rows, *, page):
            assert page == 0
            return 7

    dialog = NFePurchaseImportDialog(DurableApplication(), draft())
    assert dialog.checkpoint_status.text() == "Rascunho salvo automaticamente"
    dialog.close()


def test_falha_do_autosave_fica_visivel_e_preserva_dialogo():
    class FailingApplication(Application):
        def save_draft(self, _draft, _rows, *, page):
            raise RuntimeError("disco indisponível")

    dialog = NFePurchaseImportDialog(FailingApplication(), draft())
    assert "NÃO salvo" in dialog.checkpoint_status.text()
    assert "disco indisponível" in dialog.checkpoint_status.text()
    assert dialog.isEnabled()
    dialog.close()
