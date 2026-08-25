import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from tests.test_ui_qt_pdv import make_view_model
from ui_qt.commercial.pdv_button_style import (
    PDV_BUDGET_ACTIVE_STYLE, PDV_BUTTON_STYLE, PDV_DESTRUCTIVE_BUTTON_STYLE,
)
from ui_qt.commercial.pdv_window import PDVWindow
from ui_qt.commercial.product_search_dialog import ProductSearchDialog


APP = QApplication.instance() or QApplication([])


def test_folha_metalica_reserva_ciano_ao_foco_e_vermelho_ao_destrutivo():
    assert "qlineargradient" in PDV_BUTTON_STYLE
    assert "QPushButton:focus { border:2px solid #73c7dc; }" in PDV_BUTTON_STYLE
    assert "#d65b63" in PDV_DESTRUCTIVE_BUTTON_STYLE
    assert "#9a6700" not in PDV_BUDGET_ACTIVE_STYLE


def test_pdv_preserva_object_names_operacionais_com_novo_acabamento():
    view_model, _gateway = make_view_model()
    window = PDVWindow(view_model)
    assert window.daily_sales_button.objectName() == "primary"
    assert window.add_button.objectName() == "primary"
    assert window.checkout_button.objectName() == "checkout"
    assert window.budget_button.objectName() == "inactive"
    assert "QPushButton#checkout" in window.styleSheet()
    window._set_budget_mode(True)
    assert window.budget_button.objectName() == "budgetActive"
    assert "#9a6700" not in window.budget_button.styleSheet()
    window.close()


def test_pesquisa_ampliada_reutiliza_botoes_metalicos_sem_mudar_acao():
    style = ProductSearchDialog._style_sheet()
    assert "QPushButton#primary" in style
    assert "#73c7dc" in style
    assert "min-height:46px" in style
