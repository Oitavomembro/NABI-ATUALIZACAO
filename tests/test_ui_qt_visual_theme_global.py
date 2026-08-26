import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QVBoxLayout

from ui_qt.visual_theme import apply_global_visual_preferences


APP = QApplication.instance() or QApplication([])


def _values(background="#102030", button="#304050", text="#f1f2f3", focus="#41a5ff"):
    return {
        "window_background": background,
        "common_button_background": button,
        "text_color": text,
        "focus_color": focus,
    }


def test_tema_alcanca_janela_ja_aberta_e_preserva_seletor_semantico():
    dialog = QDialog()
    dialog.setStyleSheet(
        "QDialog{background:#000000} QPushButton{background:#111111} "
        "QPushButton#warning{background:#aa6600}"
    )
    layout = QVBoxLayout(dialog)
    common = QPushButton("Comum")
    warning = QPushButton("Alerta"); warning.setObjectName("warning")
    layout.addWidget(common); layout.addWidget(warning)
    dialog.show(); APP.processEvents()
    apply_global_visual_preferences(_values())
    style = dialog.styleSheet()
    assert style.rfind("background:#102030") > style.find("background:#000000")
    assert style.rfind("background:#304050") > style.find("background:#111111")
    assert "QPushButton#warning{background:#aa6600}" in style
    dialog.close()


def test_tema_alcanca_janela_criada_depois_da_escolha():
    apply_global_visual_preferences(_values(background="#223344", button="#445566"))
    dialog = QDialog(); dialog.setStyleSheet("QDialog{background:#000000}")
    dialog.show(); APP.processEvents()
    assert "background:#223344" in dialog.styleSheet()
    assert "background:#445566" in dialog.styleSheet()
    dialog.close()


def test_nova_previa_substitui_a_anterior_sem_acumular_regras():
    dialog = QDialog(); dialog.show(); APP.processEvents()
    apply_global_visual_preferences(_values(background="#111111"))
    apply_global_visual_preferences(_values(background="#222222"))
    assert "background:#222222" in dialog.styleSheet()
    assert "background:#111111" not in dialog.styleSheet()
    dialog.close()
