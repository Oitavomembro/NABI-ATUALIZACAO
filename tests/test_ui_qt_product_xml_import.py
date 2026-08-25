from __future__ import annotations

from decimal import Decimal
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from administration.product_xml_import_service import (
    ProductXMLCommitResult, ProductXMLDraft, ProductXMLDraftItem, ProductXMLMatch,
)
from ui_qt.commercial.product_management_dialog import (
    ProductManagementDialog, ProductXMLReviewDialog,
)


APP = QApplication.instance() or QApplication([])


def item(*, state="NOVO", matches=()):
    return ProductXMLDraftItem(
        source_item=1, code="ABC1", description="Mesa do XML",
        barcode="7890000000000", ncm="94036000", cest="0100100",
        unit="UN", cost_price=Decimal("12.34"), matches=tuple(matches),
        state=state, warnings=("Fonte XML local",),
    )


def draft(source_item=None):
    source_item = source_item or item()
    return ProductXMLDraft(
        source_name="entrada.xml", source_sha256="a" * 64,
        prepared_by="maria", items=(source_item,),
        warnings=(
            "Fonte: XML local usado somente para preparar cadastro de produtos.",
            "Protocolo e status fiscal foram ignorados; não prova autorização.",
        ),
        fingerprint="b" * 64,
    )


class Application:
    def __init__(self):
        self.commits = []

    def search(self, _term, *, limit=200):
        return ()

    def commit_xml(self, xml_draft, decisions, *, confirmed):
        self.commits.append((xml_draft, decisions, confirmed))
        return ProductXMLCommitResult((31,), (), (), xml_draft.source_sha256)


def enter(*, shift=False, repeat=False):
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        "", repeat, 1,
    )


def assert_workspace_flags(dialog):
    flags = dialog.windowFlags()
    assert flags & Qt.WindowType.WindowMinimizeButtonHint
    assert flags & Qt.WindowType.WindowMaximizeButtonHint
    assert flags & Qt.WindowType.WindowCloseButtonHint


def test_produtos_e_revisao_xml_sao_janelas_de_trabalho_com_controles_nativos():
    main = ProductManagementDialog(Application())
    review = ProductXMLReviewDialog(Application(), draft())
    assert_workspace_flags(main)
    assert_workspace_flags(review)
    assert main.minimumWidth() >= 940 and review.minimumWidth() >= 1040
    assert "F8" in main.xml_import.text()
    main.close(); review.close()


def test_revisao_mostra_fonte_limites_e_campos_documentados_sem_autorizacao():
    dialog = ProductXMLReviewDialog(Application(), draft())
    rendered = " ".join(
        dialog.table.horizontalHeaderItem(column).text()
        for column in range(dialog.table.columnCount())
    )
    assert all(label in rendered for label in (
        "Código", "Descrição", "Código de barras", "NCM", "CEST", "Un.", "Custo",
    ))
    labels = " ".join(
        child.text() for child in dialog.findChildren(QPushButton)
    )
    assert "Confirmar cadastros" in labels
    assert "autorização" in " ".join(
        child.text().casefold() for child in dialog.findChildren(QLabel)
    )
    dialog.close()


def test_ambiguidade_nao_possui_escolha_automatica_e_expoe_ids_reais():
    matches = (
        ProductXMLMatch(7, "ABC1", "", "Mesa por código"),
        ProductXMLMatch(9, "OUTRO", "7890000000000", "Mesa por barras"),
    )
    dialog = ProductXMLReviewDialog(
        Application(), draft(item(state="AMBIGUO", matches=matches)),
    )
    box = dialog._decision_boxes[0]
    assert box.currentData() == ("", None)
    assert "Escolha" in box.currentText()
    assert "ID 7" in box.itemText(1) and "ID 9" in box.itemText(2)
    box.setCurrentIndex(2)
    decision = dialog.decisions()[0]
    assert decision.action == "USE_EXISTING" and decision.existing_product_id == 9
    dialog.close()


def test_confirmacao_modal_executa_uma_vez_e_auto_repeat_nao_confirma():
    application = Application()
    dialog = ProductXMLReviewDialog(application, draft())
    assert dialog.eventFilter(dialog.confirm, enter(repeat=True)) is True
    assert application.commits == []
    with patch.object(
        QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes,
    ):
        dialog._commit()
        dialog._commit()
    assert len(application.commits) == 1
    xml_draft, decisions, confirmed = application.commits[0]
    assert xml_draft.source_name == "entrada.xml"
    assert decisions[0].action == "CREATE"
    assert confirmed is True
    dialog.close()


def test_enter_e_shift_enter_percorrem_revisao_sem_dupla_acao():
    dialog = ProductXMLReviewDialog(Application(), draft())
    dialog.show(); dialog.table.setFocus(); APP.processEvents()
    assert dialog.eventFilter(dialog.table, enter()) is True
    assert dialog.confirm.hasFocus()
    assert dialog.eventFilter(dialog.confirm, enter(shift=True)) is True
    assert dialog.table.hasFocus()
    dialog.close()
